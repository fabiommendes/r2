"""Frontmatter shown as a list of keys above a Markdown document."""

import datetime
from collections.abc import Callable, Mapping
from typing import Any

import yaml
from rich.text import Text
from textual.widgets import Static

SEPARATOR = "; "

Scalar = str | int | float | bool | datetime.date

FieldRenderer = Callable[[Any, dict[str, str]], Text | None]
"""Render the value of one key given the theme variables, or hide it with None."""


def _scalar(value: Scalar) -> str:
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def render_value(value: Any) -> Text:
    """Render a frontmatter value.

    Scalars show as they are and lists of scalars joined by a dim
    separator. Anything else shows as YAML, starting on its own line.
    """
    if isinstance(value, Scalar):
        return Text(_scalar(value))
    if isinstance(value, list) and all(isinstance(item, Scalar) for item in value):
        text = Text()
        for index, item in enumerate(value):
            if index:
                text.append(SEPARATOR, style="dim")
            text.append(_scalar(item))
        return text
    dumped = yaml.safe_dump(
        value, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return Text("\n" + dumped.rstrip("\n"))


def render_meta(
    meta: dict[str, Any],
    colors: dict[str, str],
    fields: Mapping[str, FieldRenderer] | None = None,
) -> Text:
    """Render frontmatter with one key per line, values lined up.

    Fields map keys to renderers that replace render_value for them; colors
    are the app's theme variables, handed to those renderers. Empty values
    are left out.
    """
    fields = fields or {}
    shown: dict[str, Text] = {}
    for key, value in meta.items():
        if value in (None, "", [], {}):
            continue
        renderer = fields.get(key)
        rendered = renderer(value, colors) if renderer else render_value(value)
        if rendered is not None:
            shown[key] = rendered
    width = max(map(len, shown), default=0)
    indent = " " * (width + 2)
    lines: list[Text] = []
    for key, rendered in shown.items():
        line = Text()
        line.append(f"{key:<{width}}  ", style="dim")
        # Continuation lines start under the value column.
        parts = rendered.split("\n", allow_blank=True)
        line.append_text(Text(f"\n{indent}").join(parts))
        lines.append(line)
    return Text("\n").join(lines)


class MetaBar(Static):
    """Show the frontmatter of the document on display; hide without one."""

    DEFAULT_CSS = """
    MetaBar {
        height: auto;
        padding: 0 1;
        background: $boost;
        display: none;
    }
    """

    def __init__(self, fields: Mapping[str, FieldRenderer] | None = None) -> None:
        """Fields map keys to their own renderers, as in render_meta."""
        super().__init__()
        self.fields = fields

    def show(self, meta: dict[str, Any] | None) -> None:
        self.display = bool(meta)
        colors = self.app.get_css_variables()
        self.update(render_meta(meta, colors, self.fields) if meta else "")
