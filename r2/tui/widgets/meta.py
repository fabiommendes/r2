"""Frontmatter shown as a list of keys above a Markdown document."""

import datetime
from typing import Any

import yaml
from rich.text import Text
from textual.widgets import Static

from r2.tui import theme

# Theme variable that colors the status pill, by status.
STATUS_COLORS = {
    "backlog": "panel-lighten-2",
    "todo": "primary",
    "in_progress": "warning",
    "blocked": "error",
    "deferred": "panel-lighten-2",
    "in_review": "accent",
    "completed": "success",
    "wont_fix": "panel",
    "deprecated": "panel",
}
OTHER_STATUS_COLOR = "secondary"

# Keys whose "normal" value is left out, as in the issue files.
NORMAL_KEYS = {"priority", "severity"}

SEPARATOR = "; "

Scalar = str | int | float | bool | datetime.date


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


def render_meta(meta: dict[str, Any], colors: dict[str, str]) -> Text:
    """Render frontmatter with one key per line, values lined up.

    The status shows as a pill colored from the app's theme variables.
    """
    shown = {
        key: value
        for key, value in meta.items()
        if value not in (None, "", [], {})
        and not (key in NORMAL_KEYS and value == "normal")
    }
    width = max(map(len, shown), default=0)
    indent = " " * (width + 2)
    lines: list[Text] = []
    for key, value in shown.items():
        line = Text()
        line.append(f"{key:<{width}}  ", style="dim")
        if key == "status":
            color = colors[STATUS_COLORS.get(str(value), OTHER_STATUS_COLOR)]
            line.append_text(theme.powerline((str(value).replace("_", " "), color)))
        else:
            rendered = render_value(value)
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

    def show(self, meta: dict[str, Any] | None) -> None:
        self.display = bool(meta)
        self.update(render_meta(meta, self.app.get_css_variables()) if meta else "")
