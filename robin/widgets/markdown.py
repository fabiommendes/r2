"""Browse markdown files grouped in sections."""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.await_complete import AwaitComplete
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Markdown, MarkdownViewer, Tree
from textual.widgets.markdown import MarkdownTableOfContents

from robin import theme
from robin.issues import split_frontmatter
from robin.widgets.meta import MetaBar
from robin.widgets.splitter import Splitter


class FrontmatterMarkdown(Markdown):
    """Markdown that renders the body only and reports the frontmatter apart."""

    class FrontmatterChanged(Message):
        def __init__(self, meta: dict[str, Any] | None) -> None:
            super().__init__()
            self.meta = meta

    def update(self, markdown: str) -> AwaitComplete:
        meta, body = split_frontmatter(markdown)
        self.post_message(self.FrontmatterChanged(meta))
        return super().update(body)


class DocumentViewer(MarkdownViewer):
    """Markdown viewer that follows local links and opens web links in the browser."""

    def compose(self) -> ComposeResult:
        # Same as MarkdownViewer, with the frontmatter-aware document.
        markdown = FrontmatterMarkdown(open_links=False)
        markdown.can_focus = True
        yield markdown
        yield MarkdownTableOfContents(markdown)

    async def _on_markdown_link_clicked(self, message: Markdown.LinkClicked) -> None:
        message.stop()
        if urlparse(message.href).scheme in ("http", "https", "mailto"):
            self.app.open_url(message.href)
        else:
            await self.go(message.href)


class MarkdownBrowser(Horizontal):
    """A tree of markdown files on the left and the rendered document on the right."""

    DEFAULT_CSS = """
    MarkdownBrowser > Tree {
        height: 1fr;
    }
    MarkdownBrowser > Vertical {
        width: 1fr;
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

    def compose(self) -> ComposeResult:
        tree: Tree[Path] = Tree("docs")
        tree.show_root = False
        theme.compact(tree)
        yield tree
        yield Splitter(self.key)
        with Vertical():
            yield MetaBar()
            yield DocumentViewer(show_table_of_contents=False, open_links=False)

    def on_frontmatter_markdown_frontmatter_changed(
        self, message: FrontmatterMarkdown.FrontmatterChanged
    ) -> None:
        self.query_one(MetaBar).show(message.meta)

    def load(self, root: Path) -> None:
        """List the markdown files of the project at root."""
        tree: Tree[Path] = self.query_one(Tree)
        tree.clear()
        for title, directory in self.sections.items():
            folder = root / directory
            section = tree.root.add(title, expand=True)
            for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
                section.add_leaf(str(path.relative_to(folder)), data=path)

    async def open(self, path: Path) -> None:
        self.current = path
        await self.query_one(DocumentViewer).go(path)

    async def reload(self, root: Path) -> None:
        """List the files again and show the current document as it is now."""
        self.load(root)
        if self.current is not None and self.current.exists():
            await self.open(self.current)

    async def on_tree_node_selected(self, event: Tree.NodeSelected[Path]) -> None:
        if event.node.data is not None:
            await self.open(event.node.data)
