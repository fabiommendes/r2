"""Issue files: Markdown with YAML frontmatter and a thread of comments.

The format is specified in dev/spec/issues.md. Reading is lenient, so any
Markdown file passes as an issue; writing always produces the strict format.
"""

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from r2.core import threads

OPEN_STATUSES = [
    "backlog",
    "todo",
    "in_progress",
    "blocked",
    "deferred",
    "in_review",
]
CLOSED_STATUSES = ["completed", "wont_fix", "deprecated"]
STATUSES = OPEN_STATUSES + CLOSED_STATUSES

# The status the next step of the workflow moves an issue to.
NEXT_STATUS = {
    "backlog": "todo",
    "todo": "in_progress",
    "in_progress": "completed",
    "blocked": "deferred",
    "deferred": "wont_fix",
    "in_review": "completed",
    "completed": "backlog",
    "wont_fix": "backlog",
    "deprecated": "backlog",
}

KINDS = ["defect", "enhancement", "task"]
PRIORITIES = ["low", "normal", "high", "urgent"]
SEVERITIES = ["trivial", "minor", "normal", "major", "critical"]

# Optional keys in writing order, with the default that leaves them out.
DEFAULTS: dict[str, Any] = {
    "tags": [],
    "relatedTo": [],
    "kind": None,
    "priority": "normal",
    "severity": "normal",
    "milestone": None,
    "parent": None,
    "blocks": [],
    "created": None,
    "creator": None,
    "closed": None,
}


@dataclass
class Issue(threads.Thread):
    status: str = "backlog"

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATUSES


def slugify(title: str) -> str:
    """Turn a title into a file name stem: lowercase words joined by dashes."""
    return threads.slugify(title, "issue")


def parse(text: str, slug: str = "") -> Issue:
    """Read an issue, accepting any Markdown text."""
    return threads.parse(text, Issue, slug.replace("-", " "), "backlog")


def load(path: Path) -> Issue:
    return parse(path.read_text(errors="replace"), path.stem)


def render(issue: Issue) -> str:
    """Write an issue in the strict format."""
    return threads.render(issue, "issue", DEFAULTS)


def new_issue(
    title: str,
    *,
    today: datetime.date | None = None,
    **meta: Any,
) -> Issue:
    """Create an issue in the backlog, dated today."""
    created = today or datetime.date.today()
    return Issue(title=title, meta={**meta, "created": created})


def status_order(status: str) -> tuple[int, str]:
    """Sort key that puts known statuses in lifecycle order, others last."""
    return threads.status_order(status, STATUSES)


def set_status(issue: Issue, status: str, today: datetime.date | None = None) -> None:
    """Move the issue to status, dating it when it closes."""
    if status in CLOSED_STATUSES and issue.is_open:
        issue.meta["closed"] = today or datetime.date.today()
    elif status not in CLOSED_STATUSES:
        issue.meta.pop("closed", None)
    issue.status = status
