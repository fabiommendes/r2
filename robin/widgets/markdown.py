"""Browse markdown files grouped in sections."""

from pathlib import Path
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Markdown, MarkdownViewer, Tree


class DocumentViewer(MarkdownViewer):
    """Markdown viewer that follows local links and opens web links in the browser."""

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
        width: 1fr;
        height: 1fr;
    }
    MarkdownBrowser > DocumentViewer {
        width: 3fr;
        height: 1fr;
    }
    """

    def __init__(self, sections: dict[str, str]) -> None:
        """Sections map titles to directories relative to the project root."""
        super().__init__()
        self.sections = sections

    def compose(self) -> ComposeResult:
        tree: Tree[Path] = Tree("docs")
        tree.show_root = False
        yield tree
        yield DocumentViewer(show_table_of_contents=False, open_links=False)

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
        await self.query_one(DocumentViewer).go(path)

    async def on_tree_node_selected(self, event: Tree.NodeSelected[Path]) -> None:
        if event.node.data is not None:
            await self.open(event.node.data)
