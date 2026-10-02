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


async def tail(path: Path, poll: float = 0.25) -> AsyncIterator[dict[str, Any]]:
    """Yield every event in the log, then keep yielding new ones as they arrive.

    The log may not exist yet, and it may be truncated or replaced while
    r2 runs. Lines that are not valid JSON are skipped.
    """
    position = 0
    pending = b""
    while True:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            size = 0
        if size < position:
            position, pending = 0, b""
        if size > position:
            with path.open("rb") as file:
                file.seek(position)
                chunk = file.read()
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
