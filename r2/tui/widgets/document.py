"""Markdown rendered by Rich into lines, drawn only where it shows.

Textual's Markdown mounts a widget per block, so a long document takes
seconds to lay out. Here the whole document is one widget: Rich renders it
into strips, kept for the width they were rendered at, and the Line API
draws only the rows on screen.
"""

import asyncio
import io
import re
from dataclasses import dataclass, field
from typing import ClassVar

from markdown_it import MarkdownIt
from markdown_it.token import Token
from rich import box
from rich import markdown as rich_markdown
from rich.console import Console, ConsoleOptions, JustifyMethod, RenderResult
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table as RichTable
from rich.theme import Theme
from textual import events, work
from textual.app import App
from textual.color import Color
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

# Rows rendered before update returns; the rest renders in a thread.
FIRST_ROWS = 100

# Textual's line filters expect a style on every segment, never None.
PLAIN = Style()

Highlight = tuple[int, int, Style]
"""Start and end of a span in the text of a row, and the style painted on it."""


class Heading(rich_markdown.Heading):
    """Heading aligned left, level 1 in upper case."""

    LEVEL_ALIGN: ClassVar[dict[str, JustifyMethod]] = dict.fromkeys(
        ("h1", "h2", "h3", "h4", "h5", "h6"), "left"
    )

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        text = self.text.copy()
        upper = text.plain.upper()
        # Upper casing may change the length (ß becomes SS), breaking spans.
        if self.tag == "h1" and len(upper) == len(text.plain):
            text.plain = upper
        text.justify = "left"
        yield text


class CodeBlock(rich_markdown.CodeBlock):
    """Fenced code on the fence background of the theme."""

    @classmethod
    def create(cls, markdown: rich_markdown.Markdown, token: Token) -> "CodeBlock":
        assert isinstance(markdown, Blocks)
        lexer = (token.info or "").partition(" ")[0] or "text"
        return cls(lexer, markdown.code_theme, markdown.fence_background)

    def __init__(self, lexer_name: str, theme: str, background: str) -> None:
        super().__init__(lexer_name, theme)
        self.background = background

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield Syntax(
            str(self.text).rstrip(),
            self.lexer_name,
            theme=self.theme,
            word_wrap=True,
            padding=(1, 1),
            background_color=self.background,
        )


class Table(rich_markdown.TableElement):
    """Table in a grid, with its columns aligned as the Markdown asks."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        table = RichTable(box=box.ROUNDED, style="markdown.table.border")
        if self.header is not None and self.header.row is not None:
            for column in self.header.row.cells:
                heading = column.content.copy()
                heading.stylize("markdown.table.header")
                table.add_column(heading, justify=heading.justify or "default")
        if self.body is not None:
            for row in self.body.rows:
                table.add_row(*(cell.content for cell in row.cells))
        yield table


class Blocks(rich_markdown.Markdown):
    """Rich Markdown over tokens parsed already, so a document renders in parts."""

    elements: ClassVar[dict[str, type[rich_markdown.MarkdownElement]]] = {
        **rich_markdown.Markdown.elements,
        "heading_open": Heading,
        "fence": CodeBlock,
        "code_block": CodeBlock,
        "table_open": Table,
    }

    def __init__(self, tokens: list[Token], code_theme: str, fence_background: str):
        super().__init__("", code_theme=code_theme)
        self.parsed = tokens
        self.fence_background = fence_background


@dataclass(frozen=True)
class Look:
    """What a document takes from the app theme to render."""

    theme: Theme
    code_theme: str
    fence_background: str


@dataclass
class Rendered:
    """A document rendered at a width, possibly only its first blocks."""

    width: int
    look: Look
    lines: list[Strip] = field(default_factory=list[Strip])
    plain: list[str] = field(default_factory=list[str])
    starts: list[int] = field(default_factory=list[int])
    """Row where each rendered block starts."""
    after_rule: bool = False
    """Whether the last block is a rule, which brings its own blank row."""
    complete: bool = False
    """Whether every block is rendered."""


def parse(markdown: str) -> list[list[Token]]:
    """Split markdown into its top level blocks, as tokens."""
    parser = MarkdownIt("gfm-like").enable("strikethrough").enable("table")
    blocks: list[list[Token]] = []
    block: list[Token] = []
    for token in parser.parse(markdown):
        block.append(token)
        if token.level == 0 and token.nesting <= 0:
            blocks.append(block)
            block = []
    return blocks


def heading_title(block: list[Token]) -> str | None:
    """The text of a heading block, or None for other blocks."""
    if block[0].type != "heading_open":
        return None
    inline = block[1]
    children = inline.children or []
    return "".join(c.content for c in children if c.type in ("text", "code_inline"))


def slugs(blocks: list[list[Token]]) -> dict[str, int]:
    """Anchors of the headings, GitHub style, mapped to their block."""
    anchors: dict[str, int] = {}
    seen: dict[str, int] = {}
    for index, block in enumerate(blocks):
        title = heading_title(block)
        if title is None:
            continue
        base = re.sub(r"[^\w\- ]", "", title.strip().lower()).replace(" ", "-")
        count = seen.get(base, 0)
        seen[base] = count + 1
        anchors[f"{base}-{count}" if count else base] = index
    return anchors


def blend(color: str, background: Color) -> Color:
    """Color over background, dropping its transparency."""
    return background + Color.parse(color)


def look(app: App[object]) -> Look:
    """The Rich theme of the Markdown styles, after the app theme."""
    variables = app.theme_variables
    # The document is drawn on the surface of its viewer.
    background = Color.parse(variables["surface"])
    foreground = Color.parse(variables["foreground"])
    dark = app.current_theme.dark
    fence = background.blend(Color(0, 0, 0) if dark else Color(255, 255, 255), 0.25)

    def color(name: str) -> Style:
        return Style(color=blend(variables[name], background).rich_color)

    muted = Style(color=background.blend(foreground, 0.6).rich_color)
    styles: dict[str, Style] = {
        "markdown.link": color("text-primary") + Style(underline=True),
        "markdown.link_url": color("text-primary") + Style(underline=True),
        "markdown.code": color("text-accent") + Style(bgcolor=fence.rich_color),
        "markdown.block_quote": muted,
        "markdown.hr": muted,
        "markdown.item.bullet": color("text-primary") + Style(bold=True),
        "markdown.item.number": color("text-primary"),
        "markdown.table.border": muted,
        "markdown.table.header": Style(bold=True),
    }
    for level in range(1, 7):
        name = f"markdown-h{level}"
        style = color(f"{name}-color") + Style.parse(variables[f"{name}-text-style"])
        if variables[f"{name}-background"] != "transparent":
            back = blend(variables[f"{name}-background"], background)
            style += Style(bgcolor=back.rich_color)
        styles[f"markdown.h{level}"] = style
    return Look(Theme(styles), "monokai" if dark else "default", fence.hex)


def render_blocks(
    rendered: Rendered, blocks: list[list[Token]], until: int | None = None
) -> int:
    """Render blocks onto rendered until it holds that many rows.

    Return how many blocks were rendered; all of them without until.
    """
    console = Console(
        width=rendered.width,
        file=io.StringIO(),
        color_system="truecolor",
        force_terminal=True,
        legacy_windows=False,
        theme=rendered.look.theme,
    )
    options = console.options.update(height=None)
    look = rendered.look
    for count, block in enumerate(blocks):
        if until is not None and len(rendered.lines) >= until:
            return count
        lines = console.render_lines(
            Blocks(block, look.code_theme, look.fence_background), options, pad=False
        )
        # Rich opens lists and tables with a blank row of its own; blocks keep
        # one apart. Code keeps its padding.
        if block[0].type not in ("fence", "code_block"):
            while lines and not "".join(s.text for s in lines[0]).strip():
                del lines[0]
        if not lines:
            rendered.starts.append(len(rendered.lines))
            continue
        if rendered.lines and not rendered.after_rule:
            rendered.lines.append(Strip([]))
            rendered.plain.append("")
        rendered.starts.append(len(rendered.lines))
        for line in lines:
            rendered.lines.append(
                Strip([Segment(t, s or PLAIN, c) for t, s, c in line])
            )
            rendered.plain.append("".join(segment.text for segment in line))
        rendered.after_rule = block[-1].type == "hr"
    rendered.complete = True
    return len(blocks)


def paint(strip: Strip, highlights: list[Highlight]) -> Strip:
    """Strip with each span of its text painted over in its style.

    The spans must be in order and must not overlap.
    """
    cuts: list[int] = []
    for start, end, _ in highlights:
        cuts += [strip.index_to_cell_position(start), strip.index_to_cell_position(end)]
    parts = strip.divide([*cuts, strip.cell_length])
    painted = [parts[0]]
    for index, (_, _, style) in enumerate(highlights):
        span = parts[2 * index + 1]
        painted.append(Strip(Segment.apply_style(span, post_style=style)))
        painted.append(parts[2 * index + 2])
    return Strip.join(painted)


class MarkdownDocument(Widget, can_focus=True):
    """A Markdown document as one widget that draws only its visible rows."""

    DEFAULT_CSS = """
    MarkdownDocument {
        height: auto;
        padding: 0 2;
    }
    """

    class Reflowed(Message):
        """The document rendered again at another width or theme, so its rows
        moved."""

        def __init__(self, document: "MarkdownDocument") -> None:
            super().__init__()
            self.document = document

        @property
        def control(self) -> "MarkdownDocument":
            return self.document

    class LinkClicked(Message):
        """A link in the document was clicked."""

        def __init__(self, document: "MarkdownDocument", href: str) -> None:
            super().__init__()
            self.document = document
            self.href = href

        @property
        def control(self) -> "MarkdownDocument":
            return self.document

    def __init__(self, markdown: str = "", *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._blocks = parse(markdown)
        self._anchors = slugs(self._blocks)
        self._rendered: Rendered | None = None
        self._done = asyncio.Event()
        self._reflowing = False
        self.highlights: dict[int, list[Highlight]] = {}
        """Spans painted over the rows, by row, for instance search matches."""

    @property
    def plain(self) -> list[str]:
        """The text of each row as rendered now."""
        return self._rendered.plain if self._rendered else []

    def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(
            self, lambda _: self._render_lines(force=True)
        )

    def on_resize(self) -> None:
        self._render_lines()

    def update(self, markdown: str) -> None:
        """Show markdown, rendering its first screen before return."""
        self._blocks = parse(markdown)
        self._anchors = slugs(self._blocks)
        self.highlights = {}
        self._rendered = None
        self._done.clear()
        self._render_lines()

    async def rendered(self) -> None:
        """Wait until the whole document is rendered."""
        await self._done.wait()

    def render_at(self, width: int) -> list[str]:
        """Render the whole document now, if not yet, and return its rows.

        A document not on display, like a collapsed comment, has no width; the
        caller gives the one it will most likely show at.
        """
        width = self.size.width or width
        current = self._rendered
        if current is None or current.width != width or not current.complete:
            rendered = Rendered(width, look(self.app))
            render_blocks(rendered, self._blocks)
            self._show(rendered)
            self._done.set()
        return self.plain

    def row_of(self, anchor: str) -> int | None:
        """Row of the heading with that anchor, once the document is rendered."""
        block = self._anchors.get(anchor)
        if block is None or self._rendered is None:
            return None
        starts = self._rendered.starts
        return starts[block] if block < len(starts) else None

    def _render_lines(self, force: bool = False) -> None:
        width = self.size.width
        current = self._rendered
        if not width or (not force and current and current.width == width):
            return
        self._reflowing = current is not None
        self._done.clear()
        rendered = Rendered(width, look(self.app))
        count = render_blocks(rendered, self._blocks, until=FIRST_ROWS)
        self._show(rendered)
        if count < len(self._blocks):
            self._render_rest(rendered, self._blocks[count:])
        else:
            self._complete()

    @work(thread=True, exclusive=True, group="render")
    def _render_rest(self, rendered: Rendered, blocks: list[list[Token]]) -> None:
        full = Rendered(
            rendered.width,
            rendered.look,
            list(rendered.lines),
            list(rendered.plain),
            list(rendered.starts),
            rendered.after_rule,
        )
        render_blocks(full, blocks)
        self.app.call_from_thread(self._finish, rendered, full)

    def _finish(self, started: Rendered, full: Rendered) -> None:
        # A newer render may have replaced the one this thread continued.
        if self._rendered is started:
            self._show(full)
            self._complete()

    def _show(self, rendered: Rendered) -> None:
        self._rendered = rendered
        self.refresh(layout=True)

    def _complete(self) -> None:
        self._done.set()
        if self._reflowing:
            self._reflowing = False
            self.post_message(self.Reflowed(self))

    def get_content_height(
        self, container: object, viewport: object, width: int
    ) -> int:
        return len(self._rendered.lines) if self._rendered else 0

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        if self._rendered is None or y >= len(self._rendered.lines):
            return Strip.blank(width, self.rich_style)
        strip = self._rendered.lines[y]
        if y in self.highlights:
            strip = paint(strip, self.highlights[y])
        # Rich leaves the colors of plain text unset; the widget's fill them.
        return strip.crop_extend(0, width, PLAIN).apply_style(self.rich_style)

    def on_click(self, event: events.Click) -> None:
        href = event.style.link
        if href:
            event.stop()
            self.post_message(self.LinkClicked(self, href))
