"""Read-only file viewer that can focus on a range of lines."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static, TextArea
from textual.widgets.text_area import Selection

from robin.links import Link, is_binary

# Importing the widget queries the terminal for its graphics protocol, which
# must happen before Textual takes over the terminal.
from textual_image.widget import Image  # noqa: E402  isort: skip

CONTEXT_LINES = 5

# Raster formats Pillow decodes. SVG is text, so it shows as source.
IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}

LANGUAGES = {
    ".bash": "bash",
    ".css": "css",
    ".go": "go",
    ".html": "html",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".mjs": "javascript",
    ".py": "python",
    ".rs": "rust",
    ".sh": "bash",
    ".sql": "sql",
    ".toml": "toml",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
}


class FilePreview(Vertical):
    """Show a link either as an excerpt around its lines or as the whole file."""

    DEFAULT_CSS = """
    FilePreview > Static {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    FilePreview > TextArea {
        height: 1fr;
        border: none;
    }
    FilePreview > Image {
        width: auto;
        height: auto;
        max-height: 100%;
        display: none;
    }
    """

    full: reactive[bool] = reactive(False)
    """Show the whole file instead of the excerpt around the link."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._link: Link | None = None
        self._label = ""

    def compose(self) -> ComposeResult:
        yield Static()
        yield TextArea(read_only=True, show_line_numbers=True, soft_wrap=False)
        yield Image()

    def show(self, link: Link | None, label: str = "") -> None:
        """Display link, using label as the title."""
        self._link = link
        self._label = label or (str(link.path) if link else "")
        self._update()

    def watch_full(self) -> None:
        self._update()

    def reload(self) -> None:
        """Read the file again, for instance after it was edited."""
        self._update()

    def _show_image(self, path: Path | None) -> bool:
        """Show the image at path in place of the text, or go back to text."""
        image = self.query_one(Image)
        try:
            image.image = path
        except (OSError, ValueError):
            path = None
        image.display = path is not None
        self.query_one(TextArea).display = path is None
        return path is not None

    def toggle_full(self) -> None:
        self.full = not self.full

    def _update(self) -> None:
        if not self.is_mounted:
            return
        title = self.query_one(Static)
        area = self.query_one(TextArea)
        link = self._link
        self._show_image(None)
        if link is None:
            title.update("")
            area.load_text("")
            return
        if link.path.suffix.lower() in IMAGE_SUFFIXES and self._show_image(link.path):
            title.update(f"{self._label}  [dim](image, o to open)[/]")
            return
        if is_binary(link.path):
            title.update(self._label)
            area.load_text("Binary file, not shown. Press o to open it.")
            return
        try:
            lines = link.path.read_text(errors="replace").splitlines()
        except OSError as error:
            title.update(self._label)
            area.load_text(str(error))
            return

        first = 1
        partial = link.start is not None and not self.full
        if link.start is not None and not self.full:
            first = max(1, link.start - CONTEXT_LINES)
            last = (link.end or link.start) + CONTEXT_LINES
            lines = lines[first - 1 : last]
        mode = "excerpt" if partial else "full"
        title.update(f"{self._label}  [dim]({mode}, f to toggle)[/]")

        area.language = LANGUAGES.get(link.path.suffix)
        area.load_text("\n".join(lines))
        area.line_number_start = first
        if link.start is not None:
            start_row = min(link.start - first, len(lines) - 1)
            end_row = min((link.end or link.start) - first, len(lines) - 1)
            end_column = len(lines[end_row]) if lines else 0
            area.selection = Selection(
                (max(start_row, 0), 0), (max(end_row, 0), end_column)
            )
            self.call_after_refresh(area.scroll_cursor_visible, center=True)
        else:
            area.scroll_home(animate=False)
