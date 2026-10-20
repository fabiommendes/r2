"""Follow the events log written by r2-notify and read what Claude did."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from r2.core.links import Link, extract_links, link_from_read
from r2.integrations.claude.transcript import last_turn_text

# Claude may still be writing the transcript when the Stop hook fires.
TRANSCRIPT_SETTLE_DELAY = 0.5


# r2 replays, when it starts, the events of the last REPLAY_AGE seconds,
# and at most REPLAY_COUNT of them; older links are not worth the wait.
REPLAY_AGE = 48 * 3600
REPLAY_COUNT = 50


def recent_events(
    path: Path, now: float | None = None
) -> tuple[list[dict[str, Any]], int]:
    """The events worth replaying at startup, and the log offset after them."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return [], 0
    end = data.rfind(b"\n") + 1
    cutoff = (now if now is not None else time.time()) - REPLAY_AGE
    events: list[dict[str, Any]] = []
    for line in data[:end].splitlines()[-REPLAY_COUNT:]:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("r2_time", 0) >= cutoff:
            events.append(event)
    return events, end


async def tail(
    path: Path, poll: float = 0.25, position: int = 0
) -> AsyncIterator[dict[str, Any]]:
    """Yield the events in the log after position, then new ones as they arrive.

    The log may not exist yet, and it may be truncated or replaced while
    r2 runs. Lines that are not valid JSON are skipped.
    """
    pending = b""
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            size = 0
        if size < position:
            position, pending = 0, b""
        if size > position:
            # The log may go away between the stat and the open.
            try:
                with path.open("rb") as file:
                    file.seek(position)
                    chunk = file.read()
            except FileNotFoundError:
                chunk = b""
            position += len(chunk)
            *lines, pending = (pending + chunk).split(b"\n")
            for line in lines:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
        await asyncio.sleep(poll)


async def turn_text(event: dict[str, Any]) -> str:
    """Return the text Claude wrote in the turn that a Stop event ends."""
    text: str | None = event.get("last_assistant_message")
    if text:
        return text
    if time.time() - event.get("r2_time", 0) < TRANSCRIPT_SETTLE_DELAY:
        await asyncio.sleep(TRANSCRIPT_SETTLE_DELAY)
    path = Path(event["transcript_path"])
    return await asyncio.to_thread(last_turn_text, path)


async def event_links(event: dict[str, Any], root: Path) -> list[Link]:
    """Return the file references an event brings: a Read, or a finished turn."""
    match event.get("hook_event_name"):
        case "PostToolUse" if event.get("tool_name") == "Read":
            link = link_from_read(event["tool_input"])
            return [link] if link else []
        case "Stop":
            return extract_links(await turn_text(event), root)
        case _:
            return []
