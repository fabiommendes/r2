"""Row of buttons that act on the document on display."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button

#: Prefix of the ids of the buttons, followed by the id of their command.
ID_PREFIX = "command-"

Variant = Literal["default", "primary", "success", "warning", "error"]


@dataclass(frozen=True)
class Command:
    """A button: its id comes back in CommandBar.Pressed."""

    id: str
    label: str
    variant: Variant = "default"


#: The commands for a document, given its frontmatter (None without one).
CommandProvider = Callable[[dict[str, Any] | None], list[Command]]


class CommandBar(Horizontal):
    """Buttons for the document on display; hide when there are none.

    The provider picks the buttons each time a document shows, so they can
    depend on its frontmatter.
    """

    DEFAULT_CSS = """
    CommandBar {
        height: 1;
        padding: 0 1;
        background: $panel;
        align-horizontal: right;
        display: none;
    }
    CommandBar > Button {
        margin-left: 1;
    }
    CommandBar > Button.neutral {
        background: $panel-lighten-2;
    }
    """

    class Pressed(Message):
        """The button of a command was pressed."""

        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    def __init__(self, provider: CommandProvider | None = None) -> None:
        super().__init__()
        self.provider = provider

    async def show(self, meta: dict[str, Any] | None) -> None:
        commands = self.provider(meta) if self.provider else []
        await self.remove_children()
        await self.mount_all(
            Button(
                command.label,
                id=f"{ID_PREFIX}{command.id}",
                variant=command.variant,
                # Default buttons would blend into the bar.
                classes="neutral" if command.variant == "default" else "",
                compact=True,
            )
            for command in commands
        )
        self.display = bool(commands)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id:
            self.post_message(self.Pressed(event.button.id.removeprefix(ID_PREFIX)))
