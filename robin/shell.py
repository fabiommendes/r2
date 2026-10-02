"""Run shell commands through pipes, without a terminal emulator.

Commands get no TTY, so the environment asks common tools to keep their
colors and to skip pagers.
"""

import asyncio
import contextlib
import os
import shlex
import signal
from pathlib import Path

PIPE_ENV = {
    "FORCE_COLOR": "1",
    "CLICOLOR_FORCE": "1",
    "PAGER": "cat",
    "GIT_PAGER": "cat",
}


def command_env(columns: int) -> dict[str, str]:
    """Environment for commands whose output goes to a pane of the given width."""
    return {**os.environ, **PIPE_ENV, "COLUMNS": str(columns)}


def change_directory(command: str, cwd: Path, root: Path) -> Path:
    """Resolve the target of a `cd` command; a bare `cd` goes to the project root.

    Raises NotADirectoryError if the target does not exist.
    """
    args = shlex.split(command)[1:]
    if not args:
        return root
    target = (cwd / Path(args[0]).expanduser()).resolve()
    if not target.is_dir():
        raise NotADirectoryError(args[0])
    return target


async def start(command: str, cwd: Path, columns: int) -> asyncio.subprocess.Process:
    """Start command in its own process group, with stderr merged into stdout."""
    return await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        env=command_env(columns),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )


def send_signal(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    """Signal the whole process group, so pipelines and children stop too."""
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, sig)
