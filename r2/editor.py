"""Open files in the user's terminal editor or in their default application."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

from r2.links import Link

DEFAULT_EDITOR = "micro"


def editor_command(link: Link) -> list[str]:
    """Build the command that opens link in a terminal editor.

    The editor comes from $R2_EDITOR, $EDITOR, $VISUAL or defaults to
    micro. $EDITOR goes before $VISUAL because $VISUAL often names a GUI
    editor, which would return at once instead of taking over the terminal.

    Most terminal editors (micro, vim, nvim, nano, emacs) accept "+LINE" to
    jump to a line.
    """
    editor = (
        os.environ.get("R2_EDITOR")
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
        or DEFAULT_EDITOR
    )
    command = shlex.split(editor)
    if link.start is not None:
        command.append(f"+{link.start}")
    return [*command, str(link.path)]


def shell_command() -> list[str]:
    """Return the user's interactive shell, from $SHELL."""
    return [os.environ.get("SHELL") or "/bin/sh"]


DEFAULT_IDE = "code"


def ide_command(root: Path) -> list[str]:
    """Build the command that opens the project at root in a GUI editor.

    The IDE comes from $R2_IDE, $VISUAL or defaults to VS Code.
    """
    ide = os.environ.get("R2_IDE") or os.environ.get("VISUAL") or DEFAULT_IDE
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
