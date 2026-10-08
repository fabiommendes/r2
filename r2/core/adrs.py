"""ADR files: architecture decision records kept as Markdown threads.

The format is specified in dev/spec/adrs.md. Files are named NNNN-slug.md,
and the number is the ADR's id. Reading is lenient, so any Markdown file
passes as an ADR; writing always produces the strict format.
"""

import datetime
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from r2.core import threads

FOLDER = "dev/adr"

OPEN_STATUSES = ["proposed"]
CLOSED_STATUSES = ["accepted", "rejected", "deprecated", "superseded"]
STATUSES = OPEN_STATUSES + CLOSED_STATUSES

# The quick step between statuses. Deprecated is picked from the status menu
# and superseded is set by supersede(), so neither is in the cycle.
NEXT_STATUS = {
    "proposed": "accepted",
    "accepted": "rejected",
    "rejected": "proposed",
}

# Optional keys in writing order, with the default that leaves them out.
DEFAULTS: dict[str, Any] = {
    "tags": [],
    "relatedTo": [],
    "created": None,
    "decided": None,
    "creator": None,
    "deciders": [],
    "supersedes": [],
    "supersededBy": None,
}

# The MADR sections a new ADR starts with.
SECTIONS = ["Context", "Options", "Decision", "Consequences"]

STEM_RE = re.compile(r"^(\d+)-(.*)$")


@dataclass
class Adr(threads.Thread):
    status: str = "proposed"

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATUSES


def number(stem: str) -> int | None:
    """The id in a file name stem, or None when it has no number prefix."""
    match = STEM_RE.match(stem)
    return int(match.group(1)) if match else None


def next_stem(stems: Iterable[str], title: str) -> str:
    """The file name stem of a new ADR, numbered after the existing ones."""
    last = max((n for stem in stems if (n := number(stem)) is not None), default=0)
    return f"{last + 1:04d}-{threads.slugify(title, 'adr')}"


def parse(text: str, stem: str = "") -> Adr:
    """Read an ADR, accepting any Markdown text."""
    match = STEM_RE.match(stem)
    name = match.group(2) if match else stem
    return threads.parse(text, Adr, name.replace("-", " "), "proposed")


def load(path: Path) -> Adr:
    return parse(path.read_text(errors="replace"), path.stem)


def render(adr: Adr) -> str:
    """Write an ADR in the strict format."""
    return threads.render(adr, "adr", DEFAULTS)


def new_adr(
    title: str,
    *,
    today: datetime.date | None = None,
    **meta: Any,
) -> Adr:
    """Create a proposed ADR, dated today, with empty MADR sections."""
    created = today or datetime.date.today()
    description = "\n\n".join(f"## {section}" for section in SECTIONS)
    return Adr(title=title, description=description, meta={**meta, "created": created})


def status_order(status: str) -> tuple[int, str]:
    """Sort key that puts known statuses in lifecycle order, others last."""
    return threads.status_order(status, STATUSES)


def set_status(adr: Adr, status: str, today: datetime.date | None = None) -> None:
    """Move the ADR to status, dating the decision when it leaves proposed."""
    if status in CLOSED_STATUSES and adr.is_open:
        adr.meta["decided"] = today or datetime.date.today()
    elif status not in CLOSED_STATUSES:
        adr.meta.pop("decided", None)
    if status != "superseded":
        adr.meta.pop("supersededBy", None)
    adr.status = status


def supersede(
    new: Adr,
    new_stem: str,
    old: Adr,
    old_stem: str,
    today: datetime.date | None = None,
) -> None:
    """Record on both ADRs that new replaces old."""
    supersedes = list(new.meta.get("supersedes") or [])
    if old_stem not in supersedes:
        new.meta["supersedes"] = [*supersedes, old_stem]
    set_status(old, "superseded", today)
    old.meta["supersededBy"] = new_stem


def superseded(adrs: Mapping[str, Adr]) -> dict[str, str]:
    """Map the stem of each replaced ADR to the stem of the one replacing it.

    Only supersedes counts: when an old ADR's supersededBy disagrees, the
    newer ADR's supersedes wins.
    """
    replaced: dict[str, str] = {}
    for stem, adr in adrs.items():
        for old in adr.meta.get("supersedes") or []:
            if str(old) in adrs:
                replaced[str(old)] = stem
    return replaced


def reconcile(adrs: Mapping[str, Adr]) -> None:
    """Mark as superseded the ADRs that a newer one supersedes."""
    for old, new in superseded(adrs).items():
        adrs[old].status = "superseded"
        adrs[old].meta["supersededBy"] = new


FORMAT = threads.Format(
    type="adr",
    folder=FOLDER,
    statuses=STATUSES,
    closed=CLOSED_STATUSES,
    next_status=NEXT_STATUS,
    load=load,
    render=render,
    set_status=set_status,
    reconcile=reconcile,
)
