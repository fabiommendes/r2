"""Issues kept as markdown files in the project."""

from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, Tree

from robin import theme
from robin.issues import Issue, load, matches, render, slugify, status_order
from robin.links import Link
from robin.project import ProjectContext
from robin.views.base import View
from robin.widgets.issue_form import IssueForm
from robin.widgets.markdown import MarkdownBrowser

ISSUES_DIR = "dev/issues"
SECTIONS = {"Issues": ISSUES_DIR}


def free_path(folder: Path, slug: str) -> Path:
    """Return folder/slug.md, numbered if that file already exists."""
    path = folder / f"{slug}.md"
    number = 2
    while path.exists():
        path = folder / f"{slug}-{number}.md"
        number += 1
    return path


def first_section_line(text: str) -> int:
    """The line below the first level 2 heading, where writing starts."""
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            return number + 2
    return len(lines)


class IssueBrowser(MarkdownBrowser):
    """Issues grouped by status, with a filter under the tree."""

    DEFAULT_CSS = """
    IssueBrowser > #drawer {
        height: 1fr;
    }
    IssueBrowser #filter {
        background: $boost;
    }
    """

    def __init__(self, key: str) -> None:
        super().__init__(key, SECTIONS)
        self.show_closed = False

    def compose_drawer(self) -> ComposeResult:
        tree: Tree[Path] = Tree("issues")
        tree.show_root = False
        theme.compact(tree)
        with Vertical(id="drawer"):
            yield tree
            yield Input(id="filter", placeholder="/ filter", compact=True)

    def fill(self, tree: Tree[Path], root: Path) -> None:
        query = self.query_one("#filter", Input).value
        groups: dict[str, list[tuple[Issue, Path]]] = {}
        folder = root / ISSUES_DIR
        for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
            try:
                issue = load(path)
            except OSError:
                continue
            if (self.show_closed or issue.is_open) and matches(issue, query, path.stem):
                groups.setdefault(issue.status, []).append((issue, path))
        for status in sorted(groups, key=status_order):
            items = groups[status]
            label = f"{status.replace('_', ' ')} [dim]{len(items)}[/]"
            node = tree.root.add(label, expand=True)
            for issue, path in items:
                node.add_leaf(issue.title, data=path)

    def refill(self) -> None:
        if self.root is not None:
            self.load(self.root)

    def on_input_changed(self, event: Input.Changed) -> None:
        self.refill()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one(Tree).focus()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and isinstance(self.app.focused, Input):
            self.query_one(Tree).focus()
            event.stop()


class IssuesView(View):
    ID = "issues"
    TITLE = "Issues"

    BINDINGS = [
        Binding("n", "new_issue", "New issue"),
        Binding("a", "toggle_closed", "Show closed"),
        Binding("slash", "filter", "Filter"),
    ]

    def compose(self) -> ComposeResult:
        yield IssueBrowser(self.ID)

    def action_toggle_closed(self) -> None:
        browser = self.query_one(IssueBrowser)
        browser.show_closed = not browser.show_closed
        browser.refill()

    def action_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(MarkdownBrowser).load(context.root)

    def current_link(self) -> Link | None:
        path = self.query_one(MarkdownBrowser).current
        return Link(path) if path else None

    def reload(self) -> None:
        if self.context is not None:
            browser = self.query_one(MarkdownBrowser)
            self.run_worker(browser.reload(self.context.root))

    def action_new_issue(self) -> None:
        self.app.push_screen(IssueForm(), self._create)

    def _create(self, issue: Issue | None) -> None:
        if issue is None or self.context is None:
            return
        folder = self.context.root / ISSUES_DIR
        text = render(issue)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = free_path(folder, slugify(issue.title))
            path.write_text(text)
        except OSError as error:
            self.notify(f"Could not create the issue: {error}", severity="error")
            return
        self.query_one(MarkdownBrowser).current = path
        self.post_message(self.EditFile(Link(path, first_section_line(text))))
