"""Follow the events log written by r2-notify."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any


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
