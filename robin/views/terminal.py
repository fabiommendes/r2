"""Scratch shell in the project root.

Not a terminal emulator: commands run through pipes and their output is
appended as lines. Good for quick tools, queries and test runs; programs that
need a TTY do not work. The shell resets when robin switches projects.
"""

import asyncio
import signal
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from robin import shell
from robin.project import ProjectContext
from robin.views.base import View

MAX_LINES = 5000


class TerminalView(View):
    ID = "terminal"
    TITLE = "Terminal"

    DEFAULT_CSS = """
    TerminalView {
        layout: vertical;
    }
    TerminalView > RichLog {
        height: 1fr;
        padding: 0 1;
        background: $background;
    }
    TerminalView > Horizontal {
        height: 1;
    }
    TerminalView #prompt {
        width: auto;
        padding: 0 0 0 1;
        color: $text-muted;
    }
    TerminalView Input, TerminalView Input:focus {
        height: 1;
        border: none;
        padding: 0 1;
        background: $background;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Interrupt", priority=True),
        Binding("ctrl+l", "clear", "Clear", show=False),
        Binding("up", "history(-1)", show=False),
        Binding("down", "history(1)", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._root = Path.cwd()
        self._cwd = self._root
        self._process: asyncio.subprocess.Process | None = None
        self._history: list[str] = []
        self._history_index = 0

    def compose(self) -> ComposeResult:
        yield RichLog(max_lines=MAX_LINES, wrap=True)
        with Horizontal():
            yield Static(id="prompt")
            yield Input(placeholder="command")

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        if context.root != self._root:
            self._reset(context.root)
        self._update_prompt()

    def focus_drawer(self) -> None:
        self.query_one(Input).focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Without a running process, let ctrl+c reach the input (copy).
        if action == "interrupt":
            return self._process is not None
        return True

    def _reset(self, root: Path) -> None:
        if self._process is not None:
            shell.send_signal(self._process, signal.SIGTERM)
        self._root = self._cwd = root
        self.query_one(RichLog).clear()

    def _update_prompt(self) -> None:
        if self._cwd.is_relative_to(self._root):
            relative = self._cwd.relative_to(self._root)
            location = self._root.name + ("" if relative == Path() else f"/{relative}")
        else:
            location = str(self._cwd)
        self.query_one("#prompt", Static).update(f"{location} $")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.clear()
        if not command:
            return
        if not self._history or self._history[-1] != command:
            self._history.append(command)
        self._history_index = len(self._history)

        log = self.query_one(RichLog)
        if self._process is not None:
            self.notify("A command is still running; ctrl+c stops it.")
            return
        log.write(Text.assemble(("$ ", "dim"), (command, "bold")))
        if command == "clear":
            log.clear()
        elif command == "cd" or command.startswith("cd "):
            try:
                self._cwd = shell.change_directory(command, self._cwd, self._root)
            except (NotADirectoryError, ValueError) as error:
                log.write(Text(f"cd: no such directory: {error}", style="red"))
            self._update_prompt()
        else:
            self.run_worker(self._run(command), group="terminal")

    async def _run(self, command: str) -> None:
        log = self.query_one(RichLog)
        columns = max(log.size.width - 2, 20)
        try:
            process = await shell.start(command, self._cwd, columns)
        except OSError as error:
            log.write(Text(str(error), style="red"))
            return
        self._process = process
        self.refresh_bindings()
        try:
            assert process.stdout is not None
            while line := await process.stdout.readline():
                text = line.decode(errors="replace").rstrip("\n")
                # Progress bars redraw with \r; keep only the last state.
                log.write(Text.from_ansi(text.rsplit("\r", 1)[-1]))
            code = await process.wait()
        finally:
            self._process = None
            self.refresh_bindings()
        if code == -signal.SIGINT:
            log.write(Text("interrupted", style="dim red"))
        elif code != 0:
            log.write(Text(f"exit {code}", style="dim red"))

    def action_interrupt(self) -> None:
        if self._process is not None:
            shell.send_signal(self._process, signal.SIGINT)

    def action_clear(self) -> None:
        self.query_one(RichLog).clear()

    def action_history(self, step: int) -> None:
        if not self._history:
            return
        self._history_index = max(
            0, min(self._history_index + step, len(self._history))
        )
        entry = (
            self._history[self._history_index]
            if self._history_index < len(self._history)
            else ""
        )
        prompt = self.query_one(Input)
        prompt.value = entry
        prompt.cursor_position = len(entry)
