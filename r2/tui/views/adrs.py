"""Architecture decision records kept as markdown files in the project."""

from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.binding import Binding

from r2.core.adrs import (
    FORMAT,
    Adr,
    add_supersedes,
    mark_superseded,
    new_adr,
    new_path,
)
from r2.core.threads import Thread
from r2.tui.views.threads import ThreadsView
from r2.tui.widgets.commands import Command
from r2.tui.widgets.prompts import Ask
from r2.tui.widgets.status_menu import Pick


class AdrsView(ThreadsView):
    ID = "adrs"
    TITLE = "ADRs"
    FORMAT = FORMAT
    LINK_KEYS = {"relatedTo", "supersedes", "supersededBy"}

    BINDINGS = [Binding("n", "new_adr", "New ADR")]

    def action_new_adr(self) -> None:
        self.app.push_screen(Ask("New ADR", "", "the decision to make"), self._create)

    def _create(self, title: str | None) -> None:
        if not title or not title.strip():
            return
        adr = new_adr(title.strip())
        self.create(adr, lambda folder: new_path(folder, adr.title))

    def extra_commands(self, meta: dict[str, Any]) -> list[Command]:
        return [Command("supersede", "Supersedes…")]

    def on_extra_command(self, command: str, thread: Thread, path: Path) -> None:
        if command == "supersede" and isinstance(thread, Adr):
            self._pick_superseded(thread, path)

    def _pick_superseded(self, adr: Adr, path: Path) -> None:
        """Ask which ADR the one on display replaces, and record it."""
        options = [
            (str(other), f"{escape(other.stem)}  [dim]{escape(thread.title)}[/]")
            for other, thread in sorted(self.browser.threads.items())
            if other != path and thread.status != "superseded"
        ]
        if not options:
            self.notify("No other ADR to supersede", severity="warning")
            return

        def apply(picked: str | None) -> None:
            if picked is None:
                return
            old_path = Path(picked)
            # The new ADR first: its supersedes is what counts when the
            # two disagree, so a failure between the writes is reconciled.
            try:
                FORMAT.edit(path, lambda new: add_supersedes(new, old_path.stem))
                FORMAT.edit(old_path, lambda old: mark_superseded(old, path.stem))
            except OSError as error:
                self.notify(f"Could not supersede: {error}", severity="error")
            self.reload()

        self.app.push_screen(Pick("Supersedes", options), apply)
