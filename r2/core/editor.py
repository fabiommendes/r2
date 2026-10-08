"""Open files in the user's terminal editor or in their default application."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

from r2.core.conf import Config
from r2.core.links import Link

DEFAULT_EDITOR = "micro"

# GUI editors, which take "--goto PATH:LINE" instead of "+LINE PATH". R2
# starts them detached instead of handing them the terminal.
GUI_EDITORS = {"code", "code-insiders", "codium", "cursor", "windsurf"}

# Flags that make a GUI editor block until the file is closed.
WAIT_FLAGS = {"-w", "--wait"}


def is_gui_editor(command: list[str]) -> bool:
    return bool(command) and Path(command[0]).name in GUI_EDITORS


def editor_command(link: Link) -> list[str]:
    """Build the command that opens link in a terminal editor.

    The editor comes from $R2_EDITOR, `[r2] editor` in the global config,
    $EDITOR, $VISUAL or defaults to micro. $EDITOR goes before $VISUAL
    because $VISUAL often names a GUI editor, which would return at once
    instead of taking over the terminal.

    Most terminal editors (micro, vim, nvim, nano, emacs) accept "+LINE" to
    jump to a line. VS Code and its forks read "+LINE" as a file name, so
    they get "--goto PATH:LINE" instead, and lose any wait flag: r2 starts
    them detached and never waits for them.
    """
    command = _editor()
    if is_gui_editor(command):
        command = [arg for arg in command if arg not in WAIT_FLAGS]
        if link.start is None:
            return [*command, str(link.path)]
        return [*command, "--goto", f"{link.path}:{link.start}"]
    if link.start is None:
        return [*command, str(link.path)]
    return [*command, f"+{link.start}", str(link.path)]


def _editor() -> list[str]:
    editor = (
        os.environ.get("R2_EDITOR")
        or Config().editor
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
        or DEFAULT_EDITOR
    )
    return shlex.split(editor)


def uses_gui_editor() -> bool:
    """Whether editor_command opens files in a GUI editor, which r2 does not
    wait for."""
    return is_gui_editor(_editor())


def edit_file(path: Path) -> None:
    """Open path in the terminal editor and wait for it to exit."""
    subprocess.run(editor_command(Link(path)), check=False)


def shell_command() -> list[str]:
    """Return the user's interactive shell, from $SHELL."""
    return [os.environ.get("SHELL") or "/bin/sh"]


DEFAULT_IDE = "code"


def ide_command(root: Path) -> list[str]:
    """Build the command that opens the project at root in a GUI editor.

    The IDE comes from $R2_IDE, `[r2] ide` in the global config, $VISUAL or
    defaults to VS Code.
    """
    ide = (
        os.environ.get("R2_IDE")
        or Config().ide
        or os.environ.get("VISUAL")
        or DEFAULT_IDE
    )
    return [*shlex.split(ide), str(root)]


def launch_detached(command: list[str]) -> None:
    """Start a GUI program without waiting for it.

    The program runs detached from r2's terminal, so it can neither draw
    over the UI nor read its input.
    """
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_externally(path: Path) -> None:
    """Open path in its default application, without waiting for it."""
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    launch_detached([opener, str(path)])
