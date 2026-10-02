"""Frontmatter shown as a compact bar above a Markdown document."""

import datetime
from typing import Any

from rich.text import Text
from textual.widgets import Static

from r2 import theme

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

# Keys shown in their own way; any other key is listed as "key: value".
SPECIAL_KEYS = {"type", "status", "tags", "relatedTo"}
# Keys whose "normal" value is left out, as in the issue files.
NORMAL_KEYS = {"priority", "severity"}


def _value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_value(item) for item in value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def render_meta(meta: dict[str, Any], colors: dict[str, str]) -> Text:
    """Render frontmatter as a status pill, tags, links and the other keys.

    Colors are the app's theme variables.
    """
    head = Text()
    if status := meta.get("status"):
        color = colors[STATUS_COLORS.get(str(status), OTHER_STATUS_COLOR)]
        head.append_text(theme.powerline((str(status).replace("_", " "), color)))
        head.append(" ")
    if kind := meta.get("type"):
        head.append(str(kind), style="dim")
    lines = [head] if head else []

    details = Text()
    for key, value in meta.items():
        if key in SPECIAL_KEYS or value in (None, "", []):
            continue
        if key in NORMAL_KEYS and value == "normal":
            continue
        if details:
            details.append("  ")
        details.append(f"{key} ", style="dim")
        details.append(_value(value))
    if details:
        lines.append(details)

    links = Text()
    if tags := meta.get("tags"):
        items = tags if isinstance(tags, list) else [tags]
        links.append(" ".join(f"#{tag}" for tag in items), style="italic")
    if related := meta.get("relatedTo"):
        if links:
            links.append("  ")
        links.append("→ ", style="dim")
        links.append(_value(related))
    if links:
        lines.append(links)
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
