"""
Watching `.reportlab/reports/`: the whole ingestion path of the viewer.

It is deliberately dull: it says which report changed, never what the change
was. Callers re-read the file, which makes a file deleted between the event
and the read a routine outcome, and a repeated event for one path harmless.
A missing event is not harmless, so every path in a batch is checked with a
`stat` after the batch, and reported as removed only when it is gone.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from watchfiles import awatch

from r2.core.reports.project import REPORT_SUFFIX, REVIEW_SUFFIX, Project

__all__ = ["WatchEvent", "watch_reports"]

#: Batching window, in milliseconds. A burst of writes from an agent, or a
#: rewrite done as unlink plus create, is reported once per path.
DEBOUNCE_MS = 80
STEP_MS = 20


@dataclass(frozen=True)
class WatchEvent:
    kind: Literal["report", "report-removed", "marks"]
    #: Report path under `reports/`, with no extension.
    path: str


async def watch_reports(
    project: Project,
    on_event: Callable[[WatchEvent], None],
    *,
    stop: asyncio.Event | None = None,
) -> None:
    """
    Run until stop is set or the task is cancelled.

    The watch is on `.reportlab/`, which exists for an attached project,
    rather than on `reports/`, which an agent may create later. Symlinks are
    not followed out of the project.
    """
    async for changes in awatch(
        project.reportlab,
        watch_filter=None,
        debounce=DEBOUNCE_MS,
        step=STEP_MS,
        stop_event=stop,
        recursive=True,
        rust_timeout=1000,
        yield_on_timeout=False,
    ):
        seen: dict[tuple[str, str], Path] = {}
        for _change, raw in changes:
            # inotify watches a new folder only after reporting it, so files
            # written into it right away have no event: look for them.
            changed = Path(raw)
            files = changed.rglob("*") if changed.is_dir() else [changed]
            for file in files:
                classified = classify(project, file)
                if classified is not None:
                    seen[classified] = file
        for (kind, path), file in seen.items():
            if kind == "marks":
                on_event(WatchEvent("marks", path))
            elif file.exists():
                on_event(WatchEvent("report", path))
            else:
                on_event(WatchEvent("report-removed", path))


def classify(project: Project, file: Path) -> tuple[str, str] | None:
    """(`report` or `marks`, report path), or None for anything else."""
    try:
        parts = file.relative_to(project.reports).parts
    except ValueError:
        return None
    if not parts or any(part.startswith(".") for part in parts):
        return None
    joined = "/".join(parts)
    if joined.endswith(REVIEW_SUFFIX):
        return ("marks", joined.removesuffix(REVIEW_SUFFIX))
    if joined.endswith(REPORT_SUFFIX):
        return ("report", joined.removesuffix(REPORT_SUFFIX))
    return None
