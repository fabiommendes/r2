"""Lighter look for Textual's default widgets.

Textual draws scrollbars as solid blocks and buttons as three-line boxes.
Robin replaces them with line glyphs and single-line buttons, so the UI
chrome gets out of the way of the content.
"""

from rich.color import Color, blend_rgb
from rich.segment import Segment, Segments
from rich.style import Style
from textual.scrollbar import ScrollBar, ScrollBarRender

DEFAULT_BACK = Color.parse("#555555")
DEFAULT_BAR = Color.parse("bright_magenta")

# How far the track color goes from the background toward the thumb color.
TRACK_FADE = 0.35

CSS = """
* {
    scrollbar-size-vertical: 1;
    scrollbar-size-horizontal: 1;
    scrollbar-background: $background 0%;
    scrollbar-background-hover: $background 0%;
    scrollbar-background-active: $background 0%;
    scrollbar-color: $foreground 45%;
    scrollbar-color-hover: $accent;
    scrollbar-color-active: $accent;
    scrollbar-corner-color: $background 0%;
}

Button {
    height: 1;
    min-width: 0;
    border: none;
    padding: 0 1;
}
Button:focus {
    text-style: bold;
}
"""


class ThinScrollBarRender(ScrollBarRender):
    """Draw the scrollbar as a thin line with a thicker line for the thumb."""

    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: Color = DEFAULT_BACK,
        bar_color: Color = DEFAULT_BAR,
    ) -> Segments:
        track_glyph, thumb_glyph = ("│", "┃") if vertical else ("─", "━")
        width = thickness if vertical else 1
        track_color = Color.from_triplet(
            blend_rgb(back_color.get_truecolor(), bar_color.get_truecolor(), TRACK_FADE)
        )

        def segment(glyph: str, color: Color, action: str) -> Segment:
            style = Style(color=color, bgcolor=back_color, meta={"@mouse.down": action})
            return Segment(glyph * width, style)

        size = int(size)
        if window_size and size and virtual_size > window_size:
            thumb = max(1, round(window_size * size / virtual_size))
            ratio = position / (virtual_size - window_size)
            start = min(round((size - thumb) * ratio), size - thumb)
            segments = (
                [segment(track_glyph, track_color, "scroll_up")] * start
                + [segment(thumb_glyph, bar_color, "grab")] * thumb
                + [segment(track_glyph, track_color, "scroll_down")]
                * (size - start - thumb)
            )
        else:
            segments = [Segment(" " * width, Style(bgcolor=back_color))] * size

        if vertical:
            return Segments(segments, new_lines=True)
        return Segments((segments + [Segment.line()]) * thickness, new_lines=False)


def install() -> None:
    """Make every scrollbar in the app use the thin renderer."""
    ScrollBar.renderer = ThinScrollBarRender
