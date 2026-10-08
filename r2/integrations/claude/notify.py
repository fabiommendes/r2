"""Claude Code hook that forwards events to r2.

The hook reads the event payload from stdin, tags it with the herdr pane that
runs Claude, and appends it as a single line to the events log. R2 tails
that log, so it does not need to be running when the event happens.

Tool responses are dropped: they may hold whole files and r2 does not
use them.

The hook never fails: a broken log must never block or slow down Claude.
"""

import json
import os
import sys
import time
from pathlib import Path

# Past this size the log is rotated; r2 only replays its last events anyway.
MAX_LOG_SIZE = 1024 * 1024


def events_path() -> Path:
    """Return the path of the JSONL file that collects hook events."""
    state = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(state) / "r2" / "events.jsonl"


def append_event(event: dict[str, object], path: Path) -> None:
    """Append the event to the log as a single line.

    Several Claude sessions may write to the same log concurrently. A single
    write() to a file opened with O_APPEND keeps lines from interleaving.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rotate(path)
    line = (json.dumps(event, ensure_ascii=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def rotate(path: Path, max_size: int = MAX_LOG_SIZE) -> None:
    """Move a log grown past max_size to <name>.1, replacing the previous one.

    A concurrent writer may still append its event to the moved file; only
    old events can end up there.
    """
    try:
        if path.stat().st_size > max_size:
            os.replace(path, path.with_name(path.name + ".1"))
    except FileNotFoundError:
        pass


def main() -> None:
    try:
        event = json.load(sys.stdin)
        event.pop("tool_response", None)
        event["herdr_pane_id"] = os.environ.get("HERDR_PANE_ID")
        event["r2_time"] = time.time()
        append_event(event, events_path())
    except Exception:
        pass
    sys.exit(0)
