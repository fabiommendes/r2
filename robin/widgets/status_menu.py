"""Modal menu that picks the status of an issue."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from robin.issues import CLOSED_STATUSES, STATUSES


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

    def __init__(self, current: str) -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        options = OptionList(
            *(
                Option(
                    f"[dim]{status.replace('_', ' ')}[/]"
                    if status in CLOSED_STATUSES
                    else status.replace("_", " "),
                    id=status,
                )
                for status in STATUSES
            )
        )
        options.border_title = "Status"
        if self.current in STATUSES:
            options.highlighted = STATUSES.index(self.current)
        yield options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
