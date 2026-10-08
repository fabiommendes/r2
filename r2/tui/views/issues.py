"""Issues kept as markdown files in the project."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, Tree
from textual.widgets.tree import TreeNode

from r2.core import git
from r2.core.issues import (
    CLOSED_STATUSES,
    NEXT_STATUS,
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
from r2.core.links import Link
from r2.core.project import ProjectContext
from r2.tui import theme
from r2.tui.views.base import View
from r2.tui.widgets.commands import Command, CommandBar, CommandProvider
from r2.tui.widgets.issue_form import IssueForm, split_list
from r2.tui.widgets.markdown import MarkdownBrowser
from r2.tui.widgets.meta import (
    SEPARATOR,
    FieldRenderer,
    MetaBar,
    clickable,
    render_value,
)
from r2.tui.widgets.prompts import Ask, Confirm
from r2.tui.widgets.status_menu import StatusMenu

# Theme variable that colors the status pill, by status.
STATUS_COLORS = {
    "backlog": "panel-lighten-2",
    "todo": "primary",
    "in_progress": "warning",
    "blocked": "error",
    "deferred": "panel-lighten-2",
    "in_review": "accent",
    "completed": "success",
    "wont_fix": "panel",
    "deprecated": "panel",
}
OTHER_STATUS_COLOR = "secondary"


def status_pill(value: Any, colors: dict[str, str]) -> Text:
    color = colors[STATUS_COLORS.get(str(value), OTHER_STATUS_COLOR)]
    # A click opens the status menu.
    return clickable(theme.pill(str(value).replace("_", " "), color), "status")


def unless_normal(value: Any, colors: dict[str, str]) -> Text | None:
    """Leave out the "normal" value, as the issue files do."""
    return None if value == "normal" else render_value(value)


ISSUES_DIR = "dev/issues"

LINK_MARK = " ↗"


def resolve_related(root: Path, ref: str) -> Path | None:
    """The Markdown file a relatedTo entry names, if it exists.

    An entry is either an issue slug or a path relative to the project root.
    """
    path = root / ref if ref.endswith(".md") else root / ISSUES_DIR / f"{ref}.md"
    return path if path.is_file() else None


def related_links(project_root: Callable[[], Path | None]) -> FieldRenderer:
    """Render relatedTo entries as links to the files they name.

    Entries resolve in the project that project_root returns when the
    frontmatter renders. Entries without a file show dim.
    """

    def render(value: Any, colors: dict[str, str]) -> Text:
        root = project_root()
        refs = value if isinstance(value, list) else [value]
        text = Text()
        for index, ref in enumerate(map(str, refs)):
            if index:
                text.append(SEPARATOR, style="dim")
            if root is None or resolve_related(root, ref) is None:
                text.append(ref, style="dim")
                continue
            link = Text(ref, style=f"underline {colors['text-accent']}")
            link.append(LINK_MARK, style=colors["text-accent"])
            text.append_text(clickable(link, "relatedTo", ref))
        return text

    return render


def issue_fields(project_root: Callable[[], Path | None]) -> dict[str, FieldRenderer]:
    """How the issue browser renders the frontmatter of issues."""
    return {
        "status": status_pill,
        "priority": unless_normal,
        "severity": unless_normal,
        "relatedTo": related_links(project_root),
    }


def issue_commands(meta: dict[str, Any] | None) -> list[Command]:
    """Move the issue to its next status, edit its tags or delete it."""
    if not meta or meta.get("type") != "issue":
        return []
    commands = []
    if target := NEXT_STATUS.get(str(meta.get("status"))):
        label = f"{target.replace('_', ' ')} →"
        commands.append(Command("advance", label, "primary"))
    commands.append(Command("tags", "Tags #"))
    commands.append(Command("delete", "Delete 🗑", "error"))
    return commands


SECTIONS = {"Issues": ISSUES_DIR}


def tag_list(issue: Issue) -> list[str]:
    tags = issue.meta.get("tags") or []
    return [str(tag) for tag in (tags if isinstance(tags, list) else [tags])]


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
        self.tags: dict[Path, list[str]] = {}
        """Tags of each issue, as of the last time the tree was filled."""

    def common_tags(self, limit: int = 8) -> list[str]:
        """The tags most issues have, most used first."""
        counts = Counter(tag for tags in self.tags.values() for tag in tags)
        return [tag for tag, _ in counts.most_common(limit)]

    def meta_fields(self) -> dict[str, FieldRenderer]:
        return issue_fields(lambda: self.root)

    def commands(self) -> CommandProvider:
        return issue_commands

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
        self.tags = {}
        folder = root / ISSUES_DIR
        for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
            try:
                issue = load(path)
            except OSError:
                continue
            self.tags[path] = tag_list(issue)
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

    def on_meta_bar_field_clicked(self, event: MetaBar.FieldClicked) -> None:
        if event.key == "status":
            event.stop()
            self.action_status()
        elif event.key == "relatedTo" and self.context is not None:
            event.stop()
            if path := resolve_related(self.context.root, event.value):
                self.post_message(self.OpenFile(path))

    def _current_issue(self) -> tuple[Issue, Path] | None:
        """The issue on display and its file, or None, saying why."""
        path = self.query_one(MarkdownBrowser).current
        if path is None:
            return None
        try:
            return load(path), path
        except OSError as error:
            self.notify(f"Could not read the issue: {error}", severity="error")
            return None

    def _save(self, issue: Issue, path: Path) -> None:
        try:
            path.write_text(render(issue))
        except OSError as error:
            self.notify(f"Could not save the issue: {error}", severity="error")
            return
        self.reload()

    def _move(self, issue: Issue, path: Path, status: str | None) -> None:
        if status is None or status == issue.status:
            return
        set_status(issue, status)
        self._save(issue, path)

    def action_status(self) -> None:
        if current := self._current_issue():
            self.app.push_screen(
                StatusMenu(current[0].status),
                lambda status: self._move(*current, status),
            )

    def on_command_bar_pressed(self, event: CommandBar.Pressed) -> None:
        event.stop()
        current = self._current_issue()
        if current is None:
            return
        issue, path = current
        if event.command == "advance":
            self._move(issue, path, NEXT_STATUS.get(issue.status))
        elif event.command == "tags":
            self._edit_tags(issue, path)
        elif event.command == "delete":
            self._delete(issue, path)

    def _edit_tags(self, issue: Issue, path: Path) -> None:
        def apply(answer: str | None) -> None:
            if answer is not None:
                issue.meta["tags"] = split_list(answer)
                self._save(issue, path)

        tags = tag_list(issue)
        browser = self.query_one(IssueBrowser)
        box = Ask("Tags", ", ".join(tags), "comma separated", browser.common_tags())
        self.app.push_screen(box, apply)

    def _delete(self, issue: Issue, path: Path) -> None:
        async def apply(answer: bool | None) -> None:
            if not answer:
                return
            try:
                path.unlink()
            except OSError as error:
                self.notify(f"Could not delete the issue: {error}", severity="error")
                return
            await self.query_one(MarkdownBrowser).close()
            self.reload()

        question = f"Delete {path.name}?"
        self.app.push_screen(Confirm(issue.title, question, "Delete"), apply)

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
