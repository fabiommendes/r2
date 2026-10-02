"""Client for herdr's socket API.

Herdr speaks newline-delimited JSON over a unix socket. Each request opens a
short-lived connection; focus events use a long-lived subscription.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SOCKET = Path.home() / ".config" / "herdr" / "herdr.sock"


class HerdrError(Exception):
    """Herdr rejected a request."""


@dataclass(frozen=True)
class PaneInfo:
    """The parts of a herdr pane that r2 cares about."""

    pane_id: str
    workspace_id: str
    cwd: Path
    claude_session_id: str | None


def socket_path() -> Path:
    """Return herdr's socket path, honoring HERDR_SOCKET_PATH when set."""
    return Path(os.environ.get("HERDR_SOCKET_PATH") or DEFAULT_SOCKET)


def _encode(method: str, params: dict[str, Any] | None = None) -> bytes:
    request = {"id": "r2", "method": method, "params": params or {}}
    return (json.dumps(request) + "\n").encode()


def _result(line: bytes) -> dict[str, Any]:
    response = json.loads(line)
    if "error" in response:
        raise HerdrError(response["error"])
    result: dict[str, Any] = response["result"]
    return result


async def request(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a single request and return its result."""
    reader, writer = await asyncio.open_unix_connection(socket_path())
    try:
        writer.write(_encode(method, params))
        await writer.drain()
        return _result(await reader.readline())
    finally:
        writer.close()


async def get_pane(pane_id: str) -> PaneInfo:
    """Fetch the working directory and Claude session of a pane."""
    result = await request("pane.get", {"pane_id": pane_id})
    return parse_pane(result["pane"])


def parse_pane(pane: dict[str, Any]) -> PaneInfo:
    session = pane.get("agent_session") or {}
    return PaneInfo(
        pane_id=pane["pane_id"],
        workspace_id=pane["workspace_id"],
        cwd=Path(pane["cwd"]),
        claude_session_id=session.get("value")
        if session.get("agent") == "claude"
        else None,
    )


async def focused_pane_id() -> str | None:
    """Return the pane that has focus right now."""
    result = await request("session.snapshot")
    pane_id: str | None = result["snapshot"].get("focused_pane_id")
    return pane_id


async def focus_events() -> AsyncIterator[str]:
    """Yield the id of each pane that receives focus.

    The iterator ends when herdr closes the connection, for instance when its
    server restarts. Callers are expected to reconnect.
    """
    reader, writer = await asyncio.open_unix_connection(socket_path())
    try:
        subscriptions = [{"type": "pane.focused"}]
        writer.write(_encode("events.subscribe", {"subscriptions": subscriptions}))
        await writer.drain()
        _result(await reader.readline())
        while line := await reader.readline():
            message = json.loads(line)
            if message.get("event") == "pane_focused":
                yield message["data"]["pane_id"]
    finally:
        writer.close()
