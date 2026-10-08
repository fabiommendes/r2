"""Views of threads (issues, ADRs) kept as markdown files in the project."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, Tree
from textual.widgets.tree import TreeNode

from r2.core import adrs, git, issues
from r2.core.links import Link
from r2.core.project import ProjectContext
from r2.core.threads import Format, Thread, append_stub, comment_stub, matches
from r2.tui import theme
from r2.tui.views.base import View
from r2.tui.widgets.commands import Command, CommandBar, CommandProvider
from r2.tui.widgets.issue_form import split_list
from r2.tui.widgets.markdown import MarkdownBrowser
from r2.tui.widgets.meta import SEPARATOR, FieldRenderer, MetaBar, clickable
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
    "proposed": "warning",
    "accepted": "success",
    "rejected": "error",
    "superseded": "panel",
}
OTHER_STATUS_COLOR = "secondary"


def status_pill(value: Any, colors: dict[str, str]) -> Text:
    color = colors[STATUS_COLORS.get(str(value), OTHER_STATUS_COLOR)]
    # A click opens the status menu.
    return clickable(theme.pill(str(value).replace("_", " "), color), "status")


# Folders where a bare slug in relatedTo and similar keys is looked up.
THREAD_FOLDERS = [issues.FOLDER, adrs.FOLDER]

LINK_MARK = " ↗"


def resolve_related(root: Path, ref: str) -> Path | None:
    """The Markdown file a relatedTo entry names, if it exists.

    An entry is either the file stem of an issue or an ADR, or a path
    relative to the project root.
    """
    if ref.endswith(".md"):
        candidates = [root / ref]
    else:
        candidates = [root / folder / f"{ref}.md" for folder in THREAD_FOLDERS]
    return next((path for path in candidates if path.is_file()), None)


def related_links(
    project_root: Callable[[], Path | None], key: str = "relatedTo"
) -> FieldRenderer:
    """Render the entries of key as links to the files they name.

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
            text.append_text(clickable(link, key, ref))
        return text

    return render


def thread_commands(
    format: Format[Any], extra: Callable[[dict[str, Any]], list[Command]]
) -> CommandProvider:
    """Move the thread to its next status, edit its tags or delete it.

    extra adds the commands of one kind of thread before the delete.
    """

    def commands(meta: dict[str, Any] | None) -> list[Command]:
        if not meta or meta.get("type") != format.type:
            return []
        commands = []
        if target := format.next_status.get(str(meta.get("status"))):
            label = f"{target.replace('_', ' ')} →"
            commands.append(Command("advance", label, "primary"))
        commands.append(Command("tags", "Tags #"))
        commands += extra(meta)
        commands.append(Command("delete", "Delete 🗑", "error"))
        return commands

    return commands


def tag_list(thread: Thread) -> list[str]:
    tags = thread.meta.get("tags") or []
    return [str(tag) for tag in (tags if isinstance(tags, list) else [tags])]


def first_section_line(text: str) -> int:
    """The line below the first level 2 heading, where writing starts."""
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            return number + 2
    return len(lines)


class ThreadBrowser(MarkdownBrowser):
    """Threads grouped by status, with a filter under the tree."""

    DEFAULT_CSS = """
    ThreadBrowser > #drawer {
        height: 1fr;
    }
    ThreadBrowser #filter {
        background: $boost;
    }
    """

    def __init__(
        self,
        key: str,
        title: str,
        format: Format[Any],
        fields: dict[str, FieldRenderer],
        commands: CommandProvider,
    ) -> None:
        super().__init__(key, {title: format.folder})
        self.format = format
        self.fields = fields
        self.command_provider = commands
        self.expanded: dict[str, bool] = {}
        """Groups the user opened or closed, by status."""
        self._groups: dict[TreeNode[Path], str] = {}
        self.tags: dict[Path, list[str]] = {}
        """Tags of each thread, as of the last time the tree was filled."""
        self.threads: dict[Path, Thread] = {}
        """Every thread in the folder, as of the last time the tree was filled."""

    def common_tags(self, limit: int = 8) -> list[str]:
        """The tags most threads have, most used first."""
        counts = Counter(tag for tags in self.tags.values() for tag in tags)
        return [tag for tag, _ in counts.most_common(limit)]

    def meta_fields(self) -> dict[str, FieldRenderer]:
        return self.fields

    def commands(self) -> CommandProvider:
        return self.command_provider

    def compose_drawer(self) -> ComposeResult:
        tree: Tree[Path] = Tree(self.format.type)
        tree.show_root = False
        theme.compact(tree)
        with Vertical(id="drawer"):
            yield tree
            yield Input(id="filter", placeholder="/ filter", compact=True)

    def _read(self, root: Path) -> dict[Path, Thread]:
        folder = root / self.format.folder
        found: dict[Path, Thread] = {}
        for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
            try:
                found[path] = self.format.load(path)
            except OSError:
                continue
        self.format.reconcile({path.stem: thread for path, thread in found.items()})
        return found

    def fill(self, tree: Tree[Path], root: Path) -> None:
        query = self.query_one("#filter", Input).value
        self.threads = self._read(root)
        self.tags = {path: tag_list(thread) for path, thread in self.threads.items()}
        groups: dict[str, list[tuple[Thread, Path]]] = {}
        for path, thread in self.threads.items():
            if matches(thread, query, path.stem):
                groups.setdefault(thread.status, []).append((thread, path))
        self._groups = {}
        cursor: TreeNode[Path] | None = None
        for status in sorted(groups, key=self.format.status_order):
            items = groups[status]
            label = f"{status.replace('_', ' ')} [dim]{len(items)}[/]"
            # Closed threads start folded, unless the filter or the document
            # on display asks for them.
            holds_current = any(path == self.current for _, path in items)
            expand = (
                holds_current
                or bool(query)
                or self.expanded.get(status, status not in self.format.closed)
            )
            node = tree.root.add(label, expand=expand)
            self._groups[node] = status
            for thread, path in items:
                leaf = node.add_leaf(thread.title, data=path)
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


class ThreadsView(View):
    """Base of the views that list threads of one format.

    Subclasses set FORMAT, bind "n" to a new thread and may add commands.
    """

    FORMAT: ClassVar[Format[Any]]
    LINK_KEYS: ClassVar[set[str]] = {"relatedTo"}
    """Frontmatter keys whose entries open the files they name."""

    BINDINGS = [
        Binding("c", "comment", "Comment"),
        Binding("s", "status", "Status"),
        Binding("slash", "filter", "Filter"),
    ]

    _stub: tuple[Path, str] | None = None
    """The thread file and the comment stub appended for the editor."""

    def fields(
        self, project_root: Callable[[], Path | None]
    ) -> dict[str, FieldRenderer]:
        """How the browser renders the frontmatter."""
        return {
            "status": status_pill,
            **{key: related_links(project_root, key) for key in self.LINK_KEYS},
        }

    def extra_commands(self, meta: dict[str, Any]) -> list[Command]:
        return []

    def on_extra_command(self, command: str, thread: Thread, path: Path) -> None:
        """Run a command that extra_commands added."""

    def compose(self) -> ComposeResult:
        browser = ThreadBrowser(
            self.ID,
            self.TITLE,
            self.FORMAT,
            {},
            thread_commands(self.FORMAT, self.extra_commands),
        )
        browser.fields = self.fields(lambda: browser.root)
        yield browser

    @property
    def browser(self) -> ThreadBrowser:
        return self.query_one(ThreadBrowser)

    def action_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.browser.load(context.root)

    def current_link(self) -> Link | None:
        path = self.browser.current
        return Link(path) if path else None

    def action_comment(self) -> None:
        """Open the thread in the editor with a new comment started at the end."""
        path = self.browser.current
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
        elif event.key in self.LINK_KEYS and self.context is not None:
            event.stop()
            if path := resolve_related(self.context.root, event.value):
                self.post_message(self.OpenFile(path))

    def current_thread(self) -> tuple[Thread, Path] | None:
        """The thread on display and its file, or None, saying why."""
        path = self.browser.current
        if path is None:
            return None
        try:
            return self.FORMAT.load(path), path
        except OSError as error:
            self.notify(f"Could not read the file: {error}", severity="error")
            return None

    def save(self, thread: Thread, path: Path) -> bool:
        try:
            path.write_text(self.FORMAT.render(thread))
        except OSError as error:
            self.notify(f"Could not save the file: {error}", severity="error")
            return False
        self.reload()
        return True

    def _move(self, thread: Thread, path: Path, status: str | None) -> None:
        if status is None or status == thread.status:
            return
        self.FORMAT.set_status(thread, status)
        self.save(thread, path)

    def action_status(self) -> None:
        if current := self.current_thread():
            menu = StatusMenu(
                current[0].status, self.FORMAT.statuses, self.FORMAT.closed
            )
            self.app.push_screen(menu, lambda status: self._move(*current, status))

    def on_command_bar_pressed(self, event: CommandBar.Pressed) -> None:
        event.stop()
        current = self.current_thread()
        if current is None:
            return
        thread, path = current
        if event.command == "advance":
            self._move(thread, path, self.FORMAT.next_status.get(thread.status))
        elif event.command == "tags":
            self._edit_tags(thread, path)
        elif event.command == "delete":
            self._delete(thread, path)
        else:
            self.on_extra_command(event.command, thread, path)

    def _edit_tags(self, thread: Thread, path: Path) -> None:
        def apply(answer: str | None) -> None:
            if answer is not None:
                thread.meta["tags"] = split_list(answer)
                self.save(thread, path)

        tags = tag_list(thread)
        box = Ask(
            "Tags", ", ".join(tags), "comma separated", self.browser.common_tags()
        )
        self.app.push_screen(box, apply)

    def _delete(self, thread: Thread, path: Path) -> None:
        async def apply(answer: bool | None) -> None:
            if not answer:
                return
            try:
                path.unlink()
            except OSError as error:
                self.notify(f"Could not delete the file: {error}", severity="error")
                return
            await self.browser.close()
            self.reload()

        question = f"Delete {path.name}?"
        self.app.push_screen(Confirm(thread.title, question, "Delete"), apply)

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

    def create(self, thread: Thread, path: Callable[[Path], Path]) -> None:
        """Write a new thread to the file path picks in the folder, and edit it."""
        if self.context is None:
            return
        folder = self.context.root / self.FORMAT.folder
        text = self.FORMAT.render(thread)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = path(folder)
            target.write_text(text)
        except OSError as error:
            self.notify(f"Could not create the file: {error}", severity="error")
            return
        self.browser.current = target
        self.post_message(self.EditFile(Link(target, first_section_line(text))))
