"""Browse markdown files grouped in sections."""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.geometry import Region
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Collapsible, Label, Markdown, MarkdownViewer, Static, Tree
from textual.widgets._markdown import MarkdownBlock, MarkdownFence, MarkdownH1
from textual.widgets.markdown import MarkdownTableOfContents

from r2.core.issues import Comment, parse, split_frontmatter
from r2.tui import theme
from r2.tui.widgets.meta import MetaBar
from r2.tui.widgets.search import SearchBar, describe, find_spans
from r2.tui.widgets.splitter import Splitter

# Comments of an issue shown open; older ones start collapsed.
OPEN_COMMENTS = 3

BlockMatch = tuple[MarkdownBlock, int, int]
"""A search match as the block and the span in its rendered text."""


def rendered_text(block: MarkdownBlock) -> Content:
    """The text a block shows, before any search highlight."""
    # A fence keeps its text in a label, and _content is empty until a
    # theme change sets it.
    if isinstance(block, MarkdownFence):
        return block._highlighted_code
    return block._content


def text_widget(block: MarkdownBlock) -> Widget:
    """The widget that draws the text of block."""
    if isinstance(block, MarkdownFence):
        return block.query_one(Label)
    return block


def match_row(content: Content, width: int, start: int, wrap: bool) -> int:
    """Row of the text drawn at width where the character at start lands."""
    if not wrap:
        return content.plain.count("\n", 0, start)
    plain = content.plain
    row = position = 0
    for row, line in enumerate(content.wrap(max(width, 1))):
        # Wrapping drops the spaces at the breaks, so look each line up.
        found = plain.find(line.plain, position) if line.plain else position
        if found > start:
            return max(row - 1, 0)
        position = max(found, position)
    return row


class UpperH1(MarkdownH1):
    """Level 1 heading in upper case."""

    def set_content(self, content: Content) -> None:
        upper = content.plain.upper()
        # Upper casing may change the length (ß becomes SS), breaking spans.
        if len(upper) == len(content.plain):
            content = Content(upper, list(content.spans))
        super().set_content(content)


class FrontmatterMarkdown(Markdown):
    """Markdown that renders the body only and reports the frontmatter apart.

    For issues, the body stops at the description; the comments are reported
    apart too, so they can be shown as a thread.
    """

    BLOCKS = {**Markdown.BLOCKS, "h1": UpperH1}

    class Parsed(Message):
        def __init__(self, meta: dict[str, Any] | None, comments: list[Comment]):
            super().__init__()
            self.meta = meta
            self.comments = comments

    def update(self, markdown: str) -> AwaitComplete:
        meta, body = split_frontmatter(markdown)
        comments: list[Comment] = []
        if meta is not None and meta.get("type") == "issue":
            issue = parse(markdown)
            body = f"# {issue.title}\n\n{issue.description}"
            comments = issue.comments
        self.post_message(self.Parsed(meta, comments))
        return super().update(body)


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
    CommentThread Markdown {
        margin: 0;
    }
    CommentThread MarkdownBlock:last-child {
        margin-bottom: 0;
    }
    """

    def show(self, comments: list[Comment]) -> None:
        self.remove_children()
        first_open = len(comments) - OPEN_COMMENTS
        self.mount_all(
            Collapsible(
                Markdown(comment.text),
                title=f"#{number}  {comment.author or 'comment'}",
                collapsed=number <= first_open,
            )
            for number, comment in enumerate(comments, start=1)
        )


class DocumentViewer(MarkdownViewer):
    """Markdown viewer that follows local links and opens web links in the browser."""

    def compose(self) -> ComposeResult:
        # Same as MarkdownViewer, with the frontmatter-aware document.
        markdown = FrontmatterMarkdown(open_links=False)
        markdown.can_focus = True
        yield markdown
        yield CommentThread()
        yield MarkdownTableOfContents(markdown)

    def on_frontmatter_markdown_parsed(
        self, message: FrontmatterMarkdown.Parsed
    ) -> None:
        self.query_one(CommentThread).show(message.comments)

    async def _on_markdown_link_clicked(self, message: Markdown.LinkClicked) -> None:
        message.stop()
        if urlparse(message.href).scheme in ("http", "https", "mailto"):
            self.app.open_url(message.href)
        else:
            await self.go(message.href)


class MarkdownPane(Vertical):
    """A rendered Markdown document under a bar with its frontmatter.

    / searches the text as shown, not the Markdown source, so markup and
    link targets do not match. Tables are not searched yet.
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

    def __init__(self) -> None:
        super().__init__()
        self.pattern = ""
        self.matches: list[BlockMatch] = []
        self.match_index = -1
        """Index of the selected match, or -1 before the first one."""
        self._painted: dict[MarkdownBlock, tuple[Content, Content]] = {}
        """Blocks with highlights, mapped to their text before and after."""

    def compose(self) -> ComposeResult:
        yield MetaBar()
        yield DocumentViewer(show_table_of_contents=False, open_links=False)
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

    def on_input_submitted(self, event: SearchBar.Submitted) -> None:
        if not isinstance(event.input, SearchBar):
            return
        event.stop()
        event.input.close()
        self._focus_document()
        if event.value:
            self.search(event.value)

    def search(self, pattern: str) -> int:
        """Highlight pattern, show its first match and return the count."""
        self.action_clear_search()
        self.pattern = pattern
        viewer = self.query_one(DocumentViewer)
        for block in viewer.query(MarkdownBlock):
            text = rendered_text(block).plain
            for start, end in find_spans(text, pattern):
                self.matches.append((block, start, end))
        if self.matches:
            self._select(0)
        else:
            self._show_state()
        return len(self.matches)

    def action_move(self, step: int) -> None:
        self._select((self.match_index + step) % len(self.matches))

    def action_clear_search(self) -> None:
        for block, (before, after) in self._painted.items():
            # Skip blocks the document dropped or rendered again since.
            if block.is_attached and block._content is after:
                block.set_content(before)
        self._painted.clear()
        self.pattern = ""
        self.matches = []
        self.match_index = -1
        self._show_state()

    def on_markdown_viewer_navigator_updated(self) -> None:
        # Another document is on display, so the matches point nowhere.
        self.action_clear_search()

    def _select(self, index: int) -> None:
        self.match_index = index
        self._paint()
        block = self.matches[index][0]
        for collapsible in block.ancestors_with_self:
            if isinstance(collapsible, Collapsible):
                collapsible.collapsed = False
        self._show_state()
        self.call_after_refresh(self._scroll_to_current)

    def _paint(self) -> None:
        """Highlight every match, the current one apart."""
        match_style = self.get_visual_style("markdown-pane--match")
        current_style = self.get_visual_style("markdown-pane--current")
        styled: dict[MarkdownBlock, Content] = {}
        for index, (block, start, end) in enumerate(self.matches):
            if block not in styled:
                styled[block] = self._painted.get(block, (rendered_text(block), None))[
                    0
                ]
            style = current_style if index == self.match_index else match_style
            styled[block] = styled[block].stylize(style, start, end)
        for block, after in styled.items():
            before = self._original(block)
            block.set_content(after)
            # Blocks may change the content they are given, so keep theirs.
            self._painted[block] = (before, block._content)

    def _original(self, block: MarkdownBlock) -> Content:
        """The text of block without the highlights painted on it."""
        if block in self._painted:
            return self._painted[block][0]
        return rendered_text(block)

    def _scroll_to_current(self) -> None:
        if not self.matches:
            return
        block, start, _ = self.matches[self.match_index]
        viewer = self.query_one(DocumentViewer)
        widget = text_widget(block)
        region = widget.content_region
        row = match_row(
            rendered_text(block),
            region.width,
            start,
            wrap=not isinstance(block, MarkdownFence),
        )
        y = region.y - viewer.content_region.y + viewer.scroll_offset.y + row
        viewer.scroll_to_region(Region(0, y, 1, 1), center=True, animate=False)

    def _show_state(self) -> None:
        state = self.query_one("#search-state", Static)
        markup = describe(self.pattern, self.match_index, len(self.matches))
        state.update(markup)
        state.display = bool(markup)

    def _focus_document(self) -> None:
        self.query_one(FrontmatterMarkdown).focus()

    def on_frontmatter_markdown_parsed(
        self, message: FrontmatterMarkdown.Parsed
    ) -> None:
        self.query_one(MetaBar).show(message.meta)

    async def open(self, path: Path) -> None:
        self.current = path
        self.action_clear_search()
        await self.query_one(DocumentViewer).go(path)

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
        yield MarkdownPane()

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

    async def open(self, path: Path) -> None:
        self.current = path
        await self.query_one(MarkdownPane).open(path)

    async def reload(self, root: Path) -> None:
        """List the files again and show the current document as it is now."""
        self.load(root)
        if self.current is not None and self.current.exists():
            await self.open(self.current)

    async def on_tree_node_selected(self, event: Tree.NodeSelected[Path]) -> None:
        if event.node.data is not None:
            await self.open(event.node.data)
