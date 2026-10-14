"""Issue files: Markdown with YAML frontmatter and a thread of comments.

The format is specified in dev/spec/issues.md. Reading is lenient, so any
Markdown file passes as an issue; writing always produces the strict format.
"""

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

from r2.core import threads

FOLDER = "dev/issues"

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

# The status the next step of the workflow moves an issue to. Finished work
# waits in in_review before it closes (tooling-root ADR 0003).
NEXT_STATUS = {
    "backlog": "todo",
    "todo": "in_progress",
    "in_progress": "in_review",
    "blocked": "deferred",
    "deferred": "wont_fix",
    "in_review": "completed",
    "completed": "backlog",
    "wont_fix": "backlog",
    "deprecated": "backlog",
}

Kind = Literal["defect", "enhancement", "task"]
Priority = Literal["low", "normal", "high", "urgent"]
KINDS: list[str] = list(get_args(Kind))
PRIORITIES: list[str] = list(get_args(Priority))
SEVERITIES = ["trivial", "minor", "normal", "major", "critical"]

# Body skeleton for each kind, so a new issue starts on a structure to fill
# in. The body of an enhancement is its spec.
TEMPLATES = {
    "defect": "## Steps to reproduce\n\n## Expected\n\n## Actual\n",
    "enhancement": (
        "## Context\n\n## Requirements\n\n- R1.\n  - Acceptance:\n\n## Out of scope\n"
    ),
    "task": "## Context\n\n## Done when\n",
}
DEFAULT_TEMPLATE = TEMPLATES["task"]

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

    @property
    def plan(self) -> threads.Progress | None:
        """The checkboxes ticked in the description, comments left out."""
        return threads.progress(self.description)


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


def template(kind: str | None) -> str:
    """The body skeleton of a new issue of kind, or of one without a kind."""
    return TEMPLATES.get(kind or "", DEFAULT_TEMPLATE)


def new_path(folder: Path, title: str) -> Path:
    """Return folder/slug.md for title, numbered if that file already exists."""
    slug = slugify(title)
    path = folder / f"{slug}.md"
    number = 2
    while path.exists():
        path = folder / f"{slug}-{number}.md"
        number += 1
    return path


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


FORMAT = threads.Format(
    type="issue",
    folder=FOLDER,
    statuses=STATUSES,
    closed=CLOSED_STATUSES,
    next_status=NEXT_STATUS,
    load=load,
    parse=parse,
    new=new_issue,
    new_path=new_path,
    render=render,
    set_status=set_status,
    progress=lambda issue: issue.plan,
)
