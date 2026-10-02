"""Modal form that collects the metadata of a new issue."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select

from robin.issues import KINDS, PRIORITIES, SEVERITIES, Issue, new_issue

# Body skeleton for each kind, so the editor opens on a structure to fill in.
TEMPLATES = {
    "defect": ["Steps to reproduce", "Expected", "Actual"],
    "enhancement": ["Motivation", "Proposal"],
    "task": ["Context", "Done when"],
}
DEFAULT_TEMPLATE = ["Context", "Done when"]


def template(kind: str | None) -> str:
    sections = TEMPLATES.get(kind or "", DEFAULT_TEMPLATE)
    return "\n\n".join(f"## {section}\n\n" for section in sections).rstrip() + "\n"


def split_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


class IssueForm(ModalScreen[Issue | None]):
    """Ask for the title and the main metadata; the rest is edited by hand."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "create", "Create"),
    ]

    DEFAULT_CSS = """
    IssueForm {
        align: center middle;
    }
    IssueForm > Vertical {
        width: 70;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    IssueForm Label {
        margin-top: 1;
    }
    IssueForm Horizontal {
        height: auto;
    }
    IssueForm Horizontal > Vertical {
        width: 1fr;
        height: auto;
    }
    IssueForm #buttons {
        margin-top: 1;
        align-horizontal: right;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Title")
            yield Input(id="title", placeholder="What is wrong or missing")
            with Horizontal():
                yield self._select("Kind", "kind", KINDS, None)
                yield self._select("Priority", "priority", PRIORITIES, "normal")
                yield self._select("Severity", "severity", SEVERITIES, "normal")
            yield Label("Tags")
            yield Input(id="tags", placeholder="comma separated")
            yield Label("Related to")
            yield Input(id="relatedTo", placeholder="entity slugs or paths")
            yield Label("Milestone")
            yield Input(id="milestone", placeholder="only for one milestone")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Create", id="create", variant="primary")

    def _select(
        self, label: str, id: str, values: list[str], value: str | None
    ) -> Vertical:
        select: Select[str] = Select(
            [(item, item) for item in values],
            id=id,
            value=value if value is not None else Select.NULL,
            allow_blank=value is None,
        )
        return Vertical(Label(label), select)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self.action_create()
        else:
            self.action_cancel()

    def on_input_submitted(self) -> None:
        self.action_create()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_create(self) -> None:
        title = self.query_one("#title", Input).value.strip()
        if not title:
            self.notify("The issue needs a title", severity="warning")
            self.query_one("#title", Input).focus()
            return
        meta: dict[str, Any] = {
            "tags": split_list(self.query_one("#tags", Input).value),
            "relatedTo": split_list(self.query_one("#relatedTo", Input).value),
            "milestone": self.query_one("#milestone", Input).value.strip() or None,
        }
        for key in ("kind", "priority", "severity"):
            value = self.query_one(f"#{key}", Select).value
            meta[key] = value if isinstance(value, str) else None
        issue = new_issue(title, **meta)
        issue.description = template(meta["kind"])
        self.dismiss(issue)
