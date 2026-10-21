"""
The runtime state of the daemon, in `daemon.json`: pid, port and token.

`r2 web` reads this file and starts a detached daemon when there is none, so
no command ever asks the user to remember a port.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import secrets
from collections.abc import Iterator
from datetime import datetime

from pydantic import BaseModel, ValidationError

from r2.core.files import atomic_write
from r2.web.paths import daemon_file, lock_file

__all__ = [
    "BIND_ADDRESS",
    "DEFAULT_PORT",
    "DaemonState",
    "alive",
    "clear_daemon_state",
    "daemon_lock",
    "new_token",
    "read_daemon_state",
    "read_live_daemon_state",
    "write_daemon_state",
]

DEFAULT_PORT = 7717
BIND_ADDRESS = "127.0.0.1"


class DaemonState(BaseModel):
    pid: int
    port: int
    token: str
    started: str = ""


def read_daemon_state() -> DaemonState | None:
    try:
        return DaemonState.model_validate_json(daemon_file().read_bytes())
    except (OSError, ValidationError):
        return None


def read_live_daemon_state() -> DaemonState | None:
    """A state file with a dead pid is the same as no state file."""
    state = read_daemon_state()
    return state if state is not None and alive(state.pid) else None


def write_daemon_state(state: DaemonState) -> None:
    file = daemon_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    # The token is a credential: create the file private before writing it.
    file.touch(mode=0o600, exist_ok=True)
    atomic_write(file, json.dumps(state.model_dump(), indent=2) + "\n")


def clear_daemon_state() -> None:
    daemon_file().unlink(missing_ok=True)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def now() -> str:
    return datetime.now().astimezone().isoformat()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextlib.contextmanager
def daemon_lock() -> Iterator[bool]:
    """
    Hold an exclusive lock while deciding whether to start a daemon, so two
    `r2 web` in different terminals do not both start one. Yields False when
    another process holds it. The kernel drops the lock with its holder, so a
    crashed daemon never leaves a stale one.
    """
    file = lock_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(file, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        os.close(fd)
