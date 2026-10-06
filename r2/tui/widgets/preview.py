"""Read-only file viewer that can focus on a range of lines."""

from pathlib import Path

from rich.markup import escape
from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.strip import Strip
from textual.widgets import Input, Static, TextArea
from textual.widgets.text_area import Selection

from r2.core.links import Link, is_binary

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


Match = tuple[int, int, int]
"""A search match as row, start column and end column."""


def find_matches(lines: list[str], pattern: str) -> list[Match]:
    """Find every occurrence of pattern in lines, in document order.

    The search ignores case unless pattern has an uppercase letter.
    """
    if not pattern:
        return []
    fold = pattern == pattern.lower()
    needle = pattern.lower() if fold else pattern
    matches: list[Match] = []
    for row, line in enumerate(lines):
        haystack = line.lower() if fold else line
        start = haystack.find(needle)
        while start >= 0:
            matches.append((row, start, start + len(needle)))
            start = haystack.find(needle, start + len(needle))
    return matches


class ExcerptArea(TextArea):
    """Read-only text area that dims some document rows and finds text."""

    COMPONENT_CLASSES = {"excerpt-area--match"}

    DEFAULT_CSS = """
    ExcerptArea > .excerpt-area--match {
        background: $warning 40%;
    }
    """

    BINDINGS = [
        Binding("escape", "clear_search", "Clear search"),
    ]

    class MatchChanged(Message):
        """The search or the current match changed."""

    def __init__(self) -> None:
        super().__init__(read_only=True, show_line_numbers=True, soft_wrap=False)
        self.faded_rows: set[int] = set()
        self.pattern = ""
        self.matches: list[Match] = []
        self.current = -1
        """Index of the selected match, or -1 before the first one."""

    def render_line(self, y: int) -> Strip:
        strip = super().render_line(y)
        if y + self.scroll_offset.y in self.faded_rows:
            return strip.apply_style(FADED)
        return strip

    def get_line(self, line_index: int) -> Text:
        line = super().get_line(line_index)
        if self.matches:
            style = self.get_component_rich_style("excerpt-area--match")
            for row, start, end in self.matches:
                if row == line_index:
                    line.stylize(style, start, end)
        return line

    def search(self, pattern: str) -> int:
        """Highlight pattern, select its first match and return the count."""
        self.pattern = pattern
        self.matches = find_matches(self.document.lines, pattern)
        self.current = -1
        self._redraw()
        if self.matches:
            self._select(0)
        else:
            self.post_message(self.MatchChanged())
        return len(self.matches)

    def action_clear_search(self) -> None:
        self.pattern = ""
        self.matches = []
        self.current = -1
        self._redraw()
        self.post_message(self.MatchChanged())

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Without a search, escape goes on to the widgets above.
        if action == "clear_search":
            return bool(self.matches)
        return True

    def action_cursor_up(self, select: bool = False) -> None:
        if not self.matches:
            super().action_cursor_up(select)
            return
        cursor = self.selection.end
        before = [
            i for i, (row, start, _) in enumerate(self.matches) if (row, start) < cursor
        ]
        self._select(before[-1] if before else len(self.matches) - 1)

    def action_cursor_down(self, select: bool = False) -> None:
        if not self.matches:
            super().action_cursor_down(select)
            return
        cursor = self.selection.end
        after = (
            i for i, (row, start, _) in enumerate(self.matches) if (row, start) > cursor
        )
        self._select(next(after, 0))

    def _select(self, index: int) -> None:
        self.current = index
        row, start, end = self.matches[index]
        # Select backwards so the cursor sits at the start of the match.
        self.selection = Selection((row, end), (row, start))
        self.scroll_cursor_visible(center=True)
        self.post_message(self.MatchChanged())

    def _redraw(self) -> None:
        # The line cache does not know about matches, so drop it.
        self._line_cache.clear()
        self.refresh()


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
    FilePreview > #search {
        display: none;
    }
    FilePreview > Image {
        width: auto;
        height: auto;
        max-height: 100%;
        display: none;
    }
    """

    BINDINGS = [Binding("slash", "search", "Search")]

    full: reactive[bool] = reactive(False)
    """Show the whole file instead of the excerpt around the link."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._link: Link | None = None
        self._label = ""
        self._heading = ""
        self.can_toggle = False
        """Whether the shown text has a range, so excerpt and full differ."""

    def compose(self) -> ComposeResult:
        yield Static(id="heading")
        yield Static(id="above")
        yield ExcerptArea()
        yield Static(id="rest")
        yield Image()
        yield Input(id="search", placeholder="/ search", compact=True)

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

    def _set_heading(self, markup: str) -> None:
        self._heading = markup
        self._show_heading()

    def _show_heading(self) -> None:
        """Show the heading with the search state after it."""
        area = self.query_one(ExcerptArea)
        markup = self._heading
        if area.pattern:
            pattern = escape(area.pattern)
            if area.matches:
                state = f"{area.current + 1}/{len(area.matches)}"
                markup += f"  [dim]/{pattern} {state}, ↑↓ to move, esc to clear[/]"
            else:
                markup += f"  [dim]/{pattern} not found[/]"
        self.query_one("#heading", Static).update(markup)

    def on_excerpt_area_match_changed(self, event: ExcerptArea.MatchChanged) -> None:
        event.stop()
        self._show_heading()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "search":
            return self.query_one(ExcerptArea).display
        return True

    def action_search(self) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        search.display = True
        search.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._close_search()
        if not event.value:
            return
        # An excerpt is too short to search, so show the whole file.
        if self.can_toggle and not self.full:
            self.full = True
        self.query_one(ExcerptArea).search(event.value)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and self.query_one("#search", Input).has_focus:
            event.stop()
            self._close_search()

    def _close_search(self) -> None:
        self.query_one("#search", Input).display = False
        self.query_one(ExcerptArea).focus()

    def _update(self) -> None:
        if not self.is_mounted:
            return
        area = self.query_one(ExcerptArea)
        link = self._link
        self._show_image(None)
        self.remove_class("-excerpt")
        self.query_one("#above", Static).styles.height = 0
        area.faded_rows = set()
        area.action_clear_search()
        self.can_toggle = False
        if link is None:
            self._set_heading("")
            area.load_text("")
            return
        if link.path.suffix.lower() in IMAGE_SUFFIXES and self._show_image(link.path):
            self._set_heading(f"{self._label}  [dim](image, o to open)[/]")
            return
        if is_binary(link.path):
            self._set_heading(self._label)
            area.load_text("Binary file, not shown. Press o to open it.")
            return
        try:
            lines = link.path.read_text(errors="replace").splitlines()
        except OSError as error:
            self._set_heading(self._label)
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
            self._set_heading(self._label)
        else:
            mode = "excerpt" if partial else "full"
            self._set_heading(f"{self._label}  [dim]({mode}, f to toggle)[/]")

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
