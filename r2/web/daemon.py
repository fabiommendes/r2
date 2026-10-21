"""
Starting, finding and stopping the daemon.

There is one daemon per machine, holding the lock file for its whole life.
`ensure_daemon` spawns a detached `r2 web serve` when none answers; two of
them racing is fine, since the one that loses the lock exits at once.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from r2.web.state import (
    BIND_ADDRESS,
    DEFAULT_PORT,
    DaemonState,
    clear_daemon_state,
    daemon_lock,
    new_token,
    now,
    read_live_daemon_state,
    write_daemon_state,
)

__all__ = [
    "DaemonError",
    "ensure_daemon",
    "find_static_root",
    "reachable",
    "reload",
    "serve",
    "stop_daemon",
]

STATIC_ENV = "R2_WEB_STATIC"


class DaemonError(RuntimeError):
    pass


def reachable(state: DaemonState) -> bool:
    """Is a daemon at this state actually answering?"""
    try:
        _call(state, "GET", "/api/health", timeout=1.5)
    except (OSError, urllib.error.URLError):
        return False
    return True


def reload(state: DaemonState) -> None:
    """Tell a running daemon to re-read the registry."""
    with contextlib.suppress(OSError, urllib.error.URLError):
        # A daemon that cannot be reloaded picks the project up on restart.
        _call(state, "POST", "/api/reload", timeout=2.0)


def ensure_daemon(timeout: float = 10.0) -> DaemonState:
    """Return a running daemon, starting one if needed."""
    state = read_live_daemon_state()
    if state is not None and reachable(state):
        return state
    subprocess.Popen(
        [sys.executable, "-m", "r2", "web", "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.1)
        state = read_live_daemon_state()
        if state is not None and reachable(state):
            return state
    raise DaemonError(
        f"the daemon did not start within {timeout:.0f}s; run `r2 web serve` to see why"
    )


def stop_daemon() -> bool:
    """Stop the running daemon. False when none was running."""
    state = read_live_daemon_state()
    if state is None:
        clear_daemon_state()
        return False
    with contextlib.suppress(ProcessLookupError):
        os.kill(state.pid, signal.SIGTERM)
    return True


def serve(
    port: int = DEFAULT_PORT,
    *,
    host: str = BIND_ADDRESS,
    on_ready: Callable[[DaemonState], None] | None = None,
) -> bool:
    """
    Become the daemon and serve until interrupted. False when another
    process already is the daemon, the normal outcome of two terminals
    racing.
    """
    with daemon_lock() as acquired:
        if not acquired:
            return False
        live = read_live_daemon_state()
        if live is not None and reachable(live):
            return False
        try:
            asyncio.run(_serve(_bind(host, port), on_ready))
        finally:
            clear_daemon_state()
    return True


async def _serve(
    sock: socket.socket, on_ready: Callable[[DaemonState], None] | None
) -> None:
    import uvicorn

    from r2.web.app import Viewer
    from r2.web.discover import register_found
    from r2.web.registry import load_projects
    from r2.web.settings import read_settings

    token = new_token()
    # Loading prunes: projects whose folder or config is gone leave the
    # registry before anything is served.
    viewer = Viewer(load_projects().projects, token, static_root=find_static_root())
    # Open event streams never end on their own, so shutdown does not wait.
    config = uvicorn.Config(
        viewer.asgi, log_level="warning", lifespan="on", timeout_graceful_shutdown=1
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        if task.done():
            await task
            return
        await asyncio.sleep(0.02)

    state = DaemonState(
        pid=os.getpid(), port=sock.getsockname()[1], token=token, started=now()
    )
    write_daemon_state(state)
    if on_ready is not None:
        on_ready(state)

    # In the background: the first page should not wait for a scan of the
    # user's folders. Discovery is a convenience, so a failure is ignored.
    with contextlib.suppress(OSError):
        if await asyncio.to_thread(register_found, read_settings()):
            await viewer.sync((await asyncio.to_thread(load_projects)).projects)
    await task


def _bind(host: str, port: int) -> socket.socket:
    """Bind the preferred port, or any free one when it is taken."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as error:
        if error.errno != errno.EADDRINUSE or port == 0:
            sock.close()
            raise
        sock.bind((host, 0))
    sock.listen(128)
    sock.set_inheritable(True)
    return sock


def find_static_root() -> Path | None:
    """
    The built UI, or None to serve the API only: `$R2_WEB_STATIC`, then the
    bundle packaged in the wheel, then `web/dist` of a source checkout.
    """
    here = Path(__file__).parent
    candidates = [
        Path(value) if (value := os.environ.get(STATIC_ENV)) else None,
        here / "static",
        here.parent.parent / "web" / "dist",
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "index.html").is_file():
            return candidate
    return None


def _call(state: DaemonState, method: str, path: str, *, timeout: float) -> bytes:
    request = urllib.request.Request(
        f"http://{BIND_ADDRESS}:{state.port}{path}",
        method=method,
        headers={"authorization": f"Bearer {state.token}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data: bytes = response.read()
        return data
