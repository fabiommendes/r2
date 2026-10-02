"""Read-only file viewer that can focus on a range of lines."""

from pathlib import Path

from rich.style import Style
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.strip import Strip
from textual.widgets import Static, TextArea
from textual.widgets.text_area import Selection

from r2.links import Link, is_binary

# Importing the widget queries the terminal for its graphics protocol, which
# must happen before Textual takes over the terminal.
from textual_image.widget import Image  # noqa: E402  isort: skip

# Lines shown around a link in excerpt mode: CONTEXT_LINES at full strength,
# then FADED_LINES dimmed where the file goes on beyond the excerpt.
CONTEXT_LINES = 3
FADED_LINES = 3

# Most rows of the dark band above an excerpt. The excerpt sits in the middle
# of the spare room up to this cap; the band below takes the rest.
MAX_TOP_BAND = 5

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


FADED = Style(dim=True)


def faded_rows(first: int, last: int, start: int, end: int, total: int) -> set[int]:
    """Rows of an excerpt (lines first to last) to dim around lines start-end.

    Lines more than CONTEXT_LINES away from the range fade out, but only on
    the sides where the file goes on beyond the excerpt. Rows count from 0
    at line first.
    """
    rows: set[int] = set()
    if first > 1:
        rows.update(range(0, start - CONTEXT_LINES - first))
    if last < total:
        rows.update(range(end + CONTEXT_LINES - first + 1, last - first + 1))
    return rows


class ExcerptArea(TextArea):
    """Read-only text area that dims some document rows."""

    def __init__(self) -> None:
        super().__init__(read_only=True, show_line_numbers=True, soft_wrap=False)
        self.faded_rows: set[int] = set()

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        if y + self.scroll_offset.y in self.faded_rows:
            return strip.apply_style(FADED)
        return strip


class FilePreview(Vertical):
    """Show a link either as an excerpt around its lines or as the whole file."""

    DEFAULT_CSS = """
    FilePreview > #heading {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    FilePreview > ExcerptArea, FilePreview > ExcerptArea:focus {
        height: 1fr;
        border: none;
    }
    /* Mark focus on the heading instead of a border, which shifts the text.
       Textual restyles children on focus changes only when the ancestor has
       a :focus-within rule of its own, hence the rule on FilePreview. */
    FilePreview:focus-within {
        background-tint: $background 0%;
    }
    FilePreview:focus-within > #heading {
        background: $primary-muted;
        color: $text-primary;
        text-style: bold;
    }
    FilePreview > #above, FilePreview > #rest {
        background: $surface-darken-1;
        display: none;
    }
    FilePreview > #above {
        height: 0;
    }
    FilePreview > #rest {
        height: 1fr;
    }
    FilePreview.-excerpt > ExcerptArea {
        height: auto;
        max-height: 100%;
    }
    FilePreview.-excerpt > #above, FilePreview.-excerpt > #rest {
        display: block;
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
        self.can_toggle = False
        """Whether the shown text has a range, so excerpt and full differ."""

    def compose(self) -> ComposeResult:
        yield Static(id="heading")
        yield Static(id="above")
        yield ExcerptArea()
        yield Static(id="rest")
        yield Image()

    def show(self, link: Link | None, label: str = "") -> None:
        """Display link, using label as the title."""
        self._link = link
        self._label = label or (str(link.path) if link else "")
        self._update()
        # Dims or enables the excerpt toggle in the footer.
        self.app.refresh_bindings()

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
        self.query_one(ExcerptArea).display = path is None
        # The image cannot take focus, so the preview takes it in its place.
        self.can_focus = path is not None
        return path is not None

    def on_resize(self) -> None:
        self.call_after_refresh(self._center_excerpt)

    def _center_excerpt(self) -> None:
        """Split the room the excerpt leaves between the bands around it."""
        if not self.has_class("-excerpt"):
            return
        above = self.query_one("#above", Static)
        taken = (
            self.query_one("#heading").outer_size.height
            + self.query_one(ExcerptArea).outer_size.height
        )
        spare = max(0, self.content_size.height - taken)
        height = min(MAX_TOP_BAND, spare // 2)
        if above.outer_size.height != height:
            above.styles.height = height

    def toggle_full(self) -> None:
        self.full = not self.full

    def _update(self) -> None:
        if not self.is_mounted:
            return
        title = self.query_one("#heading", Static)
        area = self.query_one(ExcerptArea)
        link = self._link
        self._show_image(None)
        self.remove_class("-excerpt")
        self.query_one("#above", Static).styles.height = 0
        area.faded_rows = set()
        self.can_toggle = False
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
            margin = CONTEXT_LINES + FADED_LINES
            first = max(1, link.start - margin)
            last = min(len(lines), (link.end or link.start) + margin)
            area.faded_rows = faded_rows(
                first, last, link.start, link.end or link.start, len(lines)
            )
            lines = lines[first - 1 : last]
            self.add_class("-excerpt")
            self.call_after_refresh(self._center_excerpt)
        self.can_toggle = link.start is not None
        if link.start is None:
            title.update(self._label)
        else:
            mode = "excerpt" if partial else "full"
            title.update(f"{self._label}  [dim]({mode}, f to toggle)[/]")

        area.language = LANGUAGES.get(link.path.suffix)
        area.load_text("\n".join(lines))
        area.line_number_start = first
        if link.start is not None:
            start_row = min(link.start - first, len(lines) - 1)
            end_row = min((link.end or link.start) - first, len(lines) - 1)
            end_column = len(lines[end_row]) if lines else 0
            # Select backwards so the cursor sits at the start of the range
            # and scrolling to it never shifts the view sideways.
            area.selection = Selection(
                (max(end_row, 0), end_column), (max(start_row, 0), 0)
            )
            self.call_after_refresh(area.scroll_cursor_visible, center=True)
        else:
            area.scroll_home(animate=False)
