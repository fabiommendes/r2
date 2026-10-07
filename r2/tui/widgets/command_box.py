"""Modal box that runs one shell command at a time and shows its output."""

import asyncio
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RichLog
from textual.worker import Worker

from r2.core.editor import shell_command


def short_path(path: Path) -> str:
    """Path with the home folder written as ~."""
    try:
        return f"~/{path.relative_to(Path.home())}".rstrip("/")
    except ValueError:
        return str(path)


class CommandRun(Vertical):
    """One command with its output, its exit status and a button to clear it.

    The output scrolls inside the block, so a long one does not push the
    other commands away.
    """

    DEFAULT_CSS = """
    CommandRun {
        height: auto;
        margin-bottom: 1;
    }
    CommandRun > #line {
        text-style: bold;
    }
    CommandRun > RichLog {
        height: auto;
        max-height: 15;
        background: $surface;
    }
    CommandRun > #footer {
        height: 1;
    }
    CommandRun #status {
        width: 1fr;
        color: $text-muted;
    }
    CommandRun #status.failed {
        color: $text-error;
    }
    """

    def __init__(self, command: str) -> None:
        super().__init__()
        self.command = command

    def compose(self) -> ComposeResult:
        yield Label(Text(f"$ {self.command}"), id="line")
        yield RichLog(wrap=True, markup=False)
        with Horizontal(id="footer"):
            yield Label("running", id="status")
            yield Button("Clear", id="clear", compact=True)

    def write(self, text: Text) -> None:
        self.query_one(RichLog).write(text)

    def finish(self, code: int) -> None:
        status = self.query_one("#status", Label)
        status.update(f"exit {code}")
        status.set_class(code != 0, "failed")

    def fail(self, error: str) -> None:
        status = self.query_one("#status", Label)
        status.update(error)
        status.add_class("failed")


class CommandBox(ModalScreen[None]):
    """Run commands in the user's shell, inside cwd, and keep their output.

    The commands run without a terminal: their input is empty, so programs
    that ask for input fail instead of hanging.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("ctrl+l", "clear_last", "Clear last"),
    ]

    DEFAULT_CSS = """
    CommandBox {
        align: center middle;
    }
    CommandBox > Vertical {
        width: 90%;
        height: 80%;
        padding: 0 1;
        border: round $primary;
        border-title-color: $text-primary;
        border-subtitle-color: $text-muted;
        background: $surface;
    }
    CommandBox #prompt {
        height: 1;
    }
    CommandBox #cwd {
        width: auto;
        color: $text-accent;
    }
    CommandBox Input {
        width: 1fr;
        background: $surface;
    }
    CommandBox #runs {
        height: 1fr;
        margin-top: 1;
    }
    """

    def __init__(self, cwd: Path) -> None:
        super().__init__()
        self.cwd = cwd
        self._process: asyncio.subprocess.Process | None = None
        self._run: Worker[None] | None = None
        #: Block of the last command run, until it is cleared.
        self._current: CommandRun | None = None

    def compose(self) -> ComposeResult:
        with Vertical() as box:
            box.border_title = f"Run in {short_path(self.cwd)}"
            box.border_subtitle = "enter run · ctrl+l clear last · esc close"
            with Horizontal(id="prompt"):
                yield Label(f"{short_path(self.cwd)} $ ", id="cwd")
                yield Input(id="command", compact=True)
            yield VerticalScroll(id="runs")

    @property
    def running(self) -> bool:
        return self._run is not None and self._run.is_running

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        if not command:
            return
        if self.running:
            self.notify("Wait for the running command or press esc", severity="warning")
            return
        event.input.value = ""
        self._run = self.run_worker(self._execute(command), exclusive=True)

    async def _execute(self, command: str) -> None:
        runs = self.query_one("#runs", VerticalScroll)
        run = self._current = CommandRun(command)
        await runs.mount(run)
        runs.scroll_end(animate=False)
        try:
            self._process = await asyncio.create_subprocess_exec(
                *shell_command(),
                "-c",
                command,
                cwd=self.cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            run.fail(str(error))
            return
        assert self._process.stdout is not None
        async for line in self._process.stdout:
            if run is self._current:
                run.write(Text.from_ansi(line.decode(errors="replace").rstrip("\n")))
        code = await self._process.wait()
        if run is self._current:
            run.finish(code)
            runs.scroll_end(animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear":
            self._clear(event.button.query_ancestor(CommandRun))

    def action_clear_last(self) -> None:
        runs = list(self.query(CommandRun))
        if runs:
            self._clear(runs[-1])

    def _clear(self, run: CommandRun) -> None:
        """Remove run, killing its command if it is still going."""
        if run is self._current:
            self._current = None
            if self.running and self._process is not None:
                self._process.kill()
        run.remove()

    def action_close(self) -> None:
        if self.running and self._process is not None:
            self._process.kill()
        self.dismiss(None)
