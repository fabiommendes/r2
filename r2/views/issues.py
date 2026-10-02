"""Issues kept as markdown files in the project."""

from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, Tree
from textual.widgets.tree import TreeNode

from r2 import git, theme
from r2.issues import (
    CLOSED_STATUSES,
    Issue,
    append_stub,
    comment_stub,
    load,
    matches,
    render,
    set_status,
    slugify,
    status_order,
)
from r2.links import Link
from r2.project import ProjectContext
from r2.views.base import View
from r2.widgets.issue_form import IssueForm
from r2.widgets.markdown import MarkdownBrowser
from r2.widgets.status_menu import StatusMenu

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
        self.expanded: dict[str, bool] = {}
        """Groups the user opened or closed, by status."""
        self._groups: dict[TreeNode[Path], str] = {}

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
            if matches(issue, query, path.stem):
                groups.setdefault(issue.status, []).append((issue, path))
        self._groups = {}
        cursor: TreeNode[Path] | None = None
        for status in sorted(groups, key=status_order):
            items = groups[status]
            label = f"{status.replace('_', ' ')} [dim]{len(items)}[/]"
            # Closed issues start folded, unless the filter or the document
            # on display asks for them.
            holds_current = any(path == self.current for _, path in items)
            expand = (
                holds_current
                or bool(query)
                or self.expanded.get(status, status not in CLOSED_STATUSES)
            )
            node = tree.root.add(label, expand=expand)
            self._groups[node] = status
            for issue, path in items:
                leaf = node.add_leaf(issue.title, data=path)
                if path == self.current:
                    cursor = leaf
        if cursor is not None:
            tree.call_after_refresh(tree.move_cursor, cursor)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[Path]) -> None:
        if status := self._groups.get(event.node):
            self.expanded[status] = True

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed[Path]) -> None:
        if status := self._groups.get(event.node):
            self.expanded[status] = False

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
        Binding("c", "comment", "Comment"),
        Binding("s", "status", "Status"),
        Binding("slash", "filter", "Filter"),
    ]

    _stub: tuple[Path, str] | None = None
    """The issue file and the comment stub appended for the editor."""

    def compose(self) -> ComposeResult:
        yield IssueBrowser(self.ID)

    def action_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(MarkdownBrowser).load(context.root)

    def current_link(self) -> Link | None:
        path = self.query_one(MarkdownBrowser).current
        return Link(path) if path else None

    def action_comment(self) -> None:
        """Open the issue in the editor with a new comment started at the end."""
        path = self.query_one(MarkdownBrowser).current
        if path is None or self.context is None:
            return
        stub = comment_stub(git.user_name(self.context.root))
        try:
            text = append_stub(path.read_text(), stub)
            path.write_text(text)
        except OSError as error:
            self.notify(f"Could not comment: {error}", severity="error")
            return
        self._stub = (path, stub)
        self.post_message(self.EditFile(Link(path, len(text.splitlines()) + 1)))

    def action_status(self) -> None:
        path = self.query_one(MarkdownBrowser).current
        if path is None:
            return
        try:
            issue = load(path)
        except OSError as error:
            self.notify(f"Could not read the issue: {error}", severity="error")
            return

        def apply(status: str | None) -> None:
            if status is None or status == issue.status:
                return
            set_status(issue, status)
            try:
                path.write_text(render(issue))
            except OSError as error:
                self.notify(f"Could not save the issue: {error}", severity="error")
                return
            self.reload()

        self.app.push_screen(StatusMenu(issue.status), apply)

    def _drop_empty_stub(self) -> None:
        """Remove the comment stub if the editor left it empty."""
        if self._stub is None:
            return
        path, stub = self._stub
        self._stub = None
        try:
            text = path.read_text()
            if text.endswith(stub):
                path.write_text(text.removesuffix(stub).rstrip("\n") + "\n")
        except OSError:
            pass

    def reload(self) -> None:
        self._drop_empty_stub()
        super().reload()

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
