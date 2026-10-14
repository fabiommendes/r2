"""RFC files: feature designs discussed as Markdown threads.

The format is specified in dev/spec/rfcs.md. Files are named slug.md, with
no number. Reading is lenient, so any Markdown file passes as an RFC;
writing always produces the strict format.
"""

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from r2.core import threads

FOLDER = "dev/rfc"

OPEN_STATUSES = ["draft"]
CLOSED_STATUSES = ["accepted", "rejected", "withdrawn"]
STATUSES = OPEN_STATUSES + CLOSED_STATUSES

# The quick step between statuses, as for ADRs. Withdrawn is picked from the
# status menu, so it only leads back to draft.
NEXT_STATUS = {
    "draft": "accepted",
    "accepted": "rejected",
    "rejected": "draft",
    "withdrawn": "draft",
}

# Optional keys in writing order, with the default that leaves them out.
DEFAULTS: dict[str, Any] = {
    "tags": [],
    "relatedTo": [],
    "created": None,
    "decided": None,
    "creator": None,
}

# The sections a new RFC starts with. Outcome stays empty until the decision.
SECTIONS = ["Problem", "Proposal", "Alternatives", "Open questions", "Outcome"]


@dataclass
class Rfc(threads.Thread):
    status: str = "draft"

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATUSES


def parse(text: str, slug: str = "") -> Rfc:
    """Read an RFC, accepting any Markdown text."""
    return threads.parse(text, Rfc, slug.replace("-", " "), "draft")


def load(path: Path) -> Rfc:
    return parse(path.read_text(errors="replace"), path.stem)


def render(rfc: Rfc) -> str:
    """Write an RFC in the strict format."""
    return threads.render(rfc, "rfc", DEFAULTS)


def new_rfc(
    title: str,
    *,
    today: datetime.date | None = None,
    **meta: Any,
) -> Rfc:
    """Create a draft RFC, dated today, with empty sections."""
    created = today or datetime.date.today()
    description = "\n\n".join(f"## {section}" for section in SECTIONS)
    return Rfc(title=title, description=description, meta={**meta, "created": created})


def new_path(folder: Path, title: str) -> Path:
    """Return folder/slug.md for title, numbered if that file already exists."""
    return threads.slug_path(folder, title, "rfc")


def status_order(status: str) -> tuple[int, str]:
    """Sort key that puts known statuses in lifecycle order, others last."""
    return threads.status_order(status, STATUSES)


def set_status(rfc: Rfc, status: str, today: datetime.date | None = None) -> None:
    """Move the RFC to status, dating the decision when it leaves draft."""
    if status in CLOSED_STATUSES and rfc.is_open:
        rfc.meta["decided"] = today or datetime.date.today()
    elif status not in CLOSED_STATUSES:
        rfc.meta.pop("decided", None)
    rfc.status = status


FORMAT = threads.Format(
    type="rfc",
    folder=FOLDER,
    statuses=STATUSES,
    closed=CLOSED_STATUSES,
    next_status=NEXT_STATUS,
    load=load,
    parse=parse,
    new=new_rfc,
    new_path=new_path,
    render=render,
    set_status=set_status,
)
