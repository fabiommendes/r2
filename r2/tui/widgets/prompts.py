"""Small modal dialogs: a yes/no question and a one-line answer."""

from collections.abc import Sequence

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

DIALOG_CSS = """
{name} {{
    align: center middle;
}}
{name} > Vertical {{
    width: 60;
    height: auto;
    padding: 0 1;
    border: round $primary;
    border-title-color: $text-primary;
    background: $surface;
}}
{name} #buttons {{
    height: 1;
    margin-top: 1;
    align-horizontal: right;
}}
{name} #buttons > Button {{
    margin-left: 1;
}}
"""


class Confirm(ModalScreen[bool]):
    """Ask a yes/no question; escape answers no."""

    BINDINGS = [Binding("escape", "answer(False)", "Cancel")]

    DEFAULT_CSS = DIALOG_CSS.format(name="Confirm")

    def __init__(self, title: str, question: str, yes: str = "Yes") -> None:
        super().__init__()
        self.title_text = title
        self.question = question
        self.yes = yes

    def compose(self) -> ComposeResult:
        with Vertical() as box:
            box.border_title = self.title_text
            yield Label(self.question)
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="no", compact=True)
                yield Button(self.yes, id="yes", variant="error", compact=True)

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.action_answer(event.button.id == "yes")

    def action_answer(self, answer: bool) -> None:
        self.dismiss(answer)


class Ask(ModalScreen[str | None]):
    """Ask for one line of text; escape gives None, enter the text.

    Choices show as buttons under the line; a click adds the choice to it
    as one more comma separated item.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = (
        DIALOG_CSS.format(name="Ask")
        + """
    Ask Input {
        background: $primary-muted;
    }
    Ask #choices {
        grid-size: 4;
        grid-gutter: 0 1;
        grid-rows: 1;
        height: auto;
        margin-top: 1;
    }
    Ask #choices > Button {
        width: 1fr;
    }
    """
    )

    def __init__(
        self,
        title: str,
        value: str = "",
        placeholder: str = "",
        choices: Sequence[str] = (),
    ) -> None:
        super().__init__()
        self.title_text = title
        self.value = value
        self.placeholder = placeholder
        self.choices = choices

    def compose(self) -> ComposeResult:
        with Vertical() as box:
            box.border_title = self.title_text
            # The cursor waits at the end, to add to the value.
            yield Input(
                self.value,
                placeholder=self.placeholder,
                select_on_focus=False,
                compact=True,
            )
            if self.choices:
                with Grid(id="choices"):
                    for choice in self.choices:
                        yield Button(choice, name=choice, compact=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        line = self.query_one(Input)
        items = [item.strip() for item in line.value.split(",") if item.strip()]
        if event.button.name and event.button.name not in items:
            line.value = ", ".join([*items, event.button.name])
        line.cursor_position = len(line.value)
        line.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
