"""Modal menu that picks the status of a thread: an issue, an ADR or an RFC."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option


class StatusMenu(ModalScreen[str | None]):
    """List the statuses, starting on the current one."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    StatusMenu {
        align: center middle;
    }
    StatusMenu > OptionList {
        width: 24;
        height: auto;
        border: round $primary;
        border-title-color: $text-primary;
        background: $surface;
        padding: 0;
    }
    """

    def __init__(self, current: str, statuses: list[str], closed: list[str]) -> None:
        super().__init__()
        self.current = current
        self.statuses = statuses
        self.closed = closed

    def compose(self) -> ComposeResult:
        options = OptionList(
            *(
                Option(
                    f"[dim]{status.replace('_', ' ')}[/]"
                    if status in self.closed
                    else status.replace("_", " "),
                    id=status,
                )
                for status in self.statuses
            )
        )
        options.border_title = "Status"
        if self.current in self.statuses:
            options.highlighted = self.statuses.index(self.current)
        yield options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class Pick(ModalScreen[str | None]):
    """List options by label and return the id of the one picked."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    Pick {
        align: center middle;
    }
    Pick > OptionList {
        width: auto;
        max-width: 80;
        height: auto;
        max-height: 20;
        border: round $primary;
        border-title-color: $text-primary;
        background: $surface;
        padding: 0;
    }
    """

    def __init__(self, title: str, options: list[tuple[str, str]]) -> None:
        super().__init__()
        self.title_text = title
        self.options = options

    def compose(self) -> ComposeResult:
        options = OptionList(*(Option(label, id=id) for id, label in self.options))
        options.border_title = self.title_text
        yield options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
