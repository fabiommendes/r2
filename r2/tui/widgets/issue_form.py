"""Modal form that collects the metadata of a new issue."""

from collections.abc import Sequence
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from r2.core.issues import KINDS, PRIORITIES, SEVERITIES, Issue, new_issue

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


class Cycle(Static, can_focus=True):
    """Pick one of a few values by stepping through them with the arrow keys.

    None stands for an unset value and is shown as a dash.
    """

    BINDINGS = [
        Binding("left", "step(-1)", "Previous", show=False),
        Binding("right", "step(1)", "Next", show=False),
    ]

    DEFAULT_CSS = """
    Cycle {
        width: 1fr;
        height: 1;
    }
    Cycle:focus {
        background: $primary-muted;
    }
    """

    index: reactive[int] = reactive(0)

    def __init__(
        self, values: Sequence[str | None], value: str | None, id: str
    ) -> None:
        super().__init__(id=id)
        self.values = values
        self.set_reactive(Cycle.index, values.index(value))

    @property
    def value(self) -> str | None:
        return self.values[self.index]

    def render(self) -> str:
        return f"[dim]‹[/] {self.value or '—'} [dim]›[/]"

    def action_step(self, delta: int) -> None:
        self.index = (self.index + delta) % len(self.values)

    def on_click(self, event: events.Click) -> None:
        self.action_step(-1 if event.x < 2 else 1)


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
    IssueForm > Grid {
        grid-size: 2;
        grid-columns: 11 1fr;
        grid-rows: 1;
        grid-gutter: 0 1;
        width: 70;
        height: auto;
        padding: 0 1;
        border: round $primary;
        border-title-color: $text-primary;
        background: $surface;
    }
    IssueForm Label {
        color: $text-muted;
    }
    IssueForm Input {
        background: $surface-lighten-1;
    }
    IssueForm Input:focus {
        background: $primary-muted;
    }
    IssueForm #buttons {
        column-span: 2;
        height: 1;
        align-horizontal: right;
    }
    """

    def compose(self) -> ComposeResult:
        with Grid() as grid:
            grid.border_title = "New issue"
            yield Label("Title")
            yield Input(
                id="title", placeholder="What is wrong or missing", compact=True
            )
            yield from self._cycle("Kind", "kind", [None, *KINDS], None)
            yield from self._cycle("Priority", "priority", PRIORITIES, "normal")
            yield from self._cycle("Severity", "severity", SEVERITIES, "normal")
            yield from self._input("Tags", "tags", "comma separated")
            yield from self._input("Related to", "relatedTo", "entity slugs or paths")
            yield from self._input("Milestone", "milestone", "only for one milestone")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel", compact=True)
                yield Button("Create", id="create", variant="primary", compact=True)

    def _input(self, label: str, id: str, placeholder: str) -> ComposeResult:
        yield Label(label)
        yield Input(id=id, placeholder=placeholder, compact=True)

    def _cycle(
        self, label: str, id: str, values: Sequence[str | None], value: str | None
    ) -> ComposeResult:
        yield Label(label)
        yield Cycle(values, value, id=id)

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
            meta[key] = self.query_one(f"#{key}", Cycle).value
        issue = new_issue(title, **meta)
        issue.description = template(meta["kind"])
        self.dismiss(issue)
