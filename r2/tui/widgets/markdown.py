"""Browse markdown files grouped in sections."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Region
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Collapsible, Static, Tree

from r2.core.threads import Comment, Thread, parse, split_frontmatter
from r2.tui import theme
from r2.tui.widgets.commands import CommandBar, CommandProvider
from r2.tui.widgets.document import MarkdownDocument
from r2.tui.widgets.meta import FieldRenderer, MetaBar
from r2.tui.widgets.search import SearchBar, describe, find_spans
from r2.tui.widgets.splitter import Splitter

# Frontmatter types whose files hold a comment thread.
THREAD_TYPES = {"issue", "adr", "rfc"}

# Comments of an issue shown open; older ones start collapsed.
OPEN_COMMENTS = 3

TextMatch = tuple[MarkdownDocument, int, int, int]
"""A search match as a document, a row of it and the span in the row text."""


def display_width(document: MarkdownDocument) -> int:
    """Width the document has, or will have once its hidden ancestors show."""
    gutter = 0
    widget: Widget = document
    while not widget.size.width and isinstance(widget.parent, Widget):
        gutter += widget.styles.gutter.width
        widget = widget.parent
    return max(widget.size.width - gutter, 1)


def read_document(path: Path) -> str:
    """The text of the file at path, or a note on why it cannot be read."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"*`{path}` is not UTF-8 text.*"
    except OSError as error:
        return f"*Cannot read `{path}`: {error.strerror or error}.*"


class FrontmatterMarkdown(MarkdownDocument):
    """Markdown that renders the body only and reports the frontmatter apart.

    For threads (issues, ADRs and RFCs), the body stops at the description; the
    comments are reported apart too, so they can be shown as a thread.
    """

    class Parsed(Message):
        def __init__(self, meta: dict[str, Any] | None, comments: list[Comment]):
            super().__init__()
            self.meta = meta
            self.comments = comments

    def update(self, markdown: str) -> None:
        meta, body = split_frontmatter(markdown)
        comments: list[Comment] = []
        if meta is not None and meta.get("type") in THREAD_TYPES:
            thread = parse(markdown, Thread, "", "")
            body = f"# {thread.title}\n\n{thread.description}"
            comments = [c for c in thread.comments if c.text.strip()]
        self.post_message(self.Parsed(meta, comments))
        super().update(body)


class CommentThread(Vertical):
    """The comments of an issue, each in a card that collapses."""

    DEFAULT_CSS = """
    CommentThread {
        height: auto;
        padding: 0 1;
    }
    CommentThread > Collapsible {
        padding: 0;
        margin-bottom: 1;
        border-top: none;
        background: $surface;
    }
    CommentThread > Collapsible > Contents {
        padding: 0 1;
    }
    CommentThread > Collapsible > CollapsibleTitle {
        width: 100%;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }
    CommentThread MarkdownDocument {
        padding: 0;
    }
    """

    def show(self, comments: list[Comment]) -> None:
        self.remove_children()
        first_open = len(comments) - OPEN_COMMENTS
        self.mount_all(
            Collapsible(
                MarkdownDocument(comment.text),
                title=f"#{number}  {comment.author or 'comment'}",
                collapsed=number <= first_open,
            )
            for number, comment in enumerate(comments, start=1)
        )


class DocumentViewer(VerticalScroll, can_focus=False, can_focus_children=True):
    """Scrolls a document and its comments, following the links in them.

    Local links open in the viewer; web links open in the browser.
    """

    DEFAULT_CSS = """
    DocumentViewer {
        height: 1fr;
        scrollbar-gutter: stable;
        background: $surface;
    }
    """

    class Navigated(Message):
        """A link took the viewer to another document."""

    location: Path | None = None
    """The file on display."""

    def compose(self) -> ComposeResult:
        yield FrontmatterMarkdown()
        yield CommentThread()

    def on_frontmatter_markdown_parsed(
        self, message: FrontmatterMarkdown.Parsed
    ) -> None:
        self.query_one(CommentThread).show(message.comments)

    async def go(self, location: str | Path) -> None:
        """Show the file at location and the heading its #anchor points to.

        A location with only an anchor stays in the file on display.
        """
        target, _, anchor = str(location).partition("#")
        document = self.query_one(FrontmatterMarkdown)
        if target:
            path = Path(target)
            self.location = path
            document.update(read_document(path))
            self.scroll_home(animate=False)
        if anchor:
            await document.rendered()
            row = document.row_of(anchor)
            if row is not None:
                self.call_after_refresh(self.scroll_to_row, document, row)

    def scroll_to_row(self, widget: Widget, row: int, *, center: bool = False) -> None:
        """Scroll until a row of a widget in the viewer shows, at the top or
        at the center."""
        y = widget.content_region.y - self.content_region.y + self.scroll_offset.y
        if center:
            self.scroll_to_region(Region(0, y + row, 1, 1), center=True, animate=False)
        else:
            self.scroll_to(y=y + row, animate=False)

    async def on_markdown_document_link_clicked(
        self, message: MarkdownDocument.LinkClicked
    ) -> None:
        message.stop()
        if urlparse(message.href).scheme in ("http", "https", "mailto"):
            self.app.open_url(message.href)
        elif message.href.startswith("#"):
            await self.go(message.href)
        else:
            # Links are relative to the file that holds them.
            parent = self.location.parent if self.location else Path()
            await self.go(parent / message.href)
            self.post_message(self.Navigated())


class MarkdownPane(Vertical):
    """A rendered Markdown document under a bar with its frontmatter.

    / searches the text as shown, not the Markdown source, so markup and
    link targets do not match, and neither does a match the wrapping splits
    between two rows.
    """

    COMPONENT_CLASSES = {"markdown-pane--match", "markdown-pane--current"}

    DEFAULT_CSS = """
    MarkdownPane {
        width: 1fr;
        height: 1fr;
    }
    MarkdownPane > .markdown-pane--match {
        background: $warning 40%;
    }
    MarkdownPane > .markdown-pane--current {
        background: $warning;
        color: $background;
    }
    MarkdownPane > #search-state {
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
        display: none;
    }
    """

    BINDINGS = [
        Binding("slash", "search", "Search"),
        # The viewer scrolls with the arrows; a search takes them over.
        Binding("up", "move(-1)", show=False, priority=True),
        Binding("down", "move(1)", show=False, priority=True),
        Binding("escape", "clear_search", "Clear search"),
    ]

    current: Path | None = None
    """The document on display."""

    def __init__(
        self,
        meta_fields: Mapping[str, FieldRenderer] | None = None,
        commands: CommandProvider | None = None,
    ) -> None:
        """Meta fields render chosen frontmatter keys their own way.

        Commands, if given, pick the buttons shown above the document.
        """
        super().__init__()
        self.meta_fields = meta_fields
        self.commands = commands
        self.pattern = ""
        self.matches: list[TextMatch] = []
        self.match_index = -1
        """Index of the selected match, or -1 before the first one."""

    def compose(self) -> ComposeResult:
        yield MetaBar(self.meta_fields)
        yield CommandBar(self.commands)
        yield DocumentViewer()
        yield Static(id="search-state")
        yield SearchBar()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Without a search, the arrows and escape go on to the widgets below.
        if action in ("move", "clear_search"):
            return bool(self.matches)
        return True

    def action_search(self) -> None:
        self.query_one(SearchBar).open()

    def on_search_bar_cancelled(self, event: SearchBar.Cancelled) -> None:
        event.stop()
        self._focus_document()

    async def on_input_submitted(self, event: SearchBar.Submitted) -> None:
        if not isinstance(event.input, SearchBar):
            return
        event.stop()
        event.input.close()
        self._focus_document()
        if event.value:
            await self.query_one(FrontmatterMarkdown).rendered()
            self.search(event.value)

    def search(self, pattern: str) -> int:
        """Highlight pattern, show its first match and return the count."""
        self.action_clear_search()
        self.pattern = pattern
        for document in self.query_one(DocumentViewer).query(MarkdownDocument):
            rows = document.render_at(display_width(document))
            for row, text in enumerate(rows):
                for start, end in find_spans(text, pattern):
                    self.matches.append((document, row, start, end))
        if self.matches:
            self._select(0)
        else:
            self._show_state()
        return len(self.matches)

    def action_move(self, step: int) -> None:
        self._select((self.match_index + step) % len(self.matches))

    def action_clear_search(self) -> None:
        for document in self.query(MarkdownDocument):
            if document.highlights:
                document.highlights = {}
                document.refresh()
        self.pattern = ""
        self.matches = []
        self.match_index = -1
        self._show_state()

    def on_document_viewer_navigated(self) -> None:
        # Another document is on display, so the matches point nowhere.
        self.action_clear_search()

    def on_markdown_document_reflowed(self, event: MarkdownDocument.Reflowed) -> None:
        # The rows moved, so the matches must be found again.
        if self.matches:
            index = self.match_index
            self.search(self.pattern)
            if self.matches and index > 0:
                self._select(min(index, len(self.matches) - 1))

    def _select(self, index: int) -> None:
        self.match_index = index
        self._paint()
        document = self.matches[index][0]
        for collapsible in document.ancestors_with_self:
            if isinstance(collapsible, Collapsible):
                collapsible.collapsed = False
        self._show_state()
        self.call_after_refresh(self._scroll_to_current)

    def _paint(self) -> None:
        """Highlight every match, the current one apart."""
        match_style = self.get_component_rich_style("markdown-pane--match")
        current_style = self.get_component_rich_style("markdown-pane--current")
        for document in self.query(MarkdownDocument):
            document.highlights = {}
        for index, (document, row, start, end) in enumerate(self.matches):
            style = current_style if index == self.match_index else match_style
            document.highlights.setdefault(row, []).append((start, end, style))
        for document in self.query(MarkdownDocument):
            document.refresh()

    def _scroll_to_current(self) -> None:
        if not self.matches:
            return
        document, row, _, _ = self.matches[self.match_index]
        self.query_one(DocumentViewer).scroll_to_row(document, row, center=True)

    def _show_state(self) -> None:
        state = self.query_one("#search-state", Static)
        markup = describe(self.pattern, self.match_index, len(self.matches))
        state.update(markup)
        state.display = bool(markup)

    def _focus_document(self) -> None:
        self.query_one(FrontmatterMarkdown).focus()

    async def on_frontmatter_markdown_parsed(
        self, message: FrontmatterMarkdown.Parsed
    ) -> None:
        self.query_one(MetaBar).show(message.meta)
        await self.query_one(CommandBar).show(message.meta)

    async def open(self, path: Path) -> None:
        self.current = path
        self.action_clear_search()
        await self.query_one(DocumentViewer).go(path)

    async def close(self) -> None:
        """Show no document."""
        self.current = None
        self.action_clear_search()
        self.query_one(FrontmatterMarkdown).update("")

    async def reload(self) -> None:
        """Show the current document as it is now."""
        if self.current is not None and self.current.exists():
            await self.open(self.current)


class MarkdownBrowser(Horizontal):
    """A tree of markdown files on the left and the rendered document on the right."""

    DEFAULT_CSS = """
    MarkdownBrowser Tree {
        height: 1fr;
    }
    """

    class Selected(Message):
        """The user picked a document in the tree and it is on display."""

    def __init__(self, key: str, sections: dict[str, str]) -> None:
        """Sections map titles to directories relative to the project root.

        Key identifies the browser's splitter in the saved settings.
        """
        super().__init__()
        self.key = key
        self.sections = sections
        self.current: Path | None = None
        """The document on display."""
        self.root: Path | None = None

    def compose(self) -> ComposeResult:
        yield from self.compose_drawer()
        yield Splitter(self.key)
        yield MarkdownPane(self.meta_fields(), self.commands())

    def meta_fields(self) -> Mapping[str, FieldRenderer]:
        """Frontmatter keys the document pane renders its own way."""
        return {}

    def commands(self) -> CommandProvider | None:
        """Buttons for the document on display; None shows no bar."""
        return None

    def compose_drawer(self) -> ComposeResult:
        """The left side; its first focusable widget must be the tree."""
        tree: Tree[Path] = Tree("docs")
        tree.show_root = False
        theme.compact(tree)
        yield tree

    def load(self, root: Path) -> None:
        """List the markdown files of the project at root."""
        self.root = root
        tree: Tree[Path] = self.query_one(Tree)
        tree.clear()
        self.fill(tree, root)

    def fill(self, tree: "Tree[Path]", root: Path) -> None:
        """Add a node for each section and a leaf for each of its files."""
        for title, directory in self.sections.items():
            folder = root / directory
            section = tree.root.add(title, expand=True)
            for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
                section.add_leaf(str(path.relative_to(folder)), data=path)

    def contains(self, path: Path) -> bool:
        """Whether path is a Markdown file in one of the sections."""
        if self.root is None or path.suffix.lower() != ".md":
            return False
        folders = [self.root / directory for directory in self.sections.values()]
        return any(path.is_relative_to(folder) for folder in folders)

    async def open(self, path: Path) -> None:
        self.current = path
        self.reveal(path)
        await self.query_one(MarkdownPane).open(path)

    async def close(self) -> None:
        """Show no document, for instance after the current one is deleted."""
        self.current = None
        await self.query_one(MarkdownPane).close()

    def reveal(self, path: Path) -> None:
        """Move the tree cursor to the leaf of path, unfolding its section."""
        tree: Tree[Path] = self.query_one(Tree)
        nodes = list(tree.root.children)
        while nodes:
            node = nodes.pop(0)
            if node.data == path:
                parent = node.parent
                while parent is not None and parent is not tree.root:
                    parent.expand()
                    parent = parent.parent
                # The cursor can only land once the unfolded nodes are laid out.
                tree.call_after_refresh(tree.move_cursor, node)
                return
            nodes.extend(node.children)

    async def reload(self, root: Path) -> None:
        """List the files again and show the current document as it is now."""
        self.load(root)
        if self.current is not None and self.current.exists():
            await self.open(self.current)

    async def on_tree_node_selected(self, event: Tree.NodeSelected[Path]) -> None:
        if event.node.data is not None:
            await self.open(event.node.data)
            self.post_message(self.Selected())
