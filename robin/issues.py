"""Issue files: Markdown with YAML frontmatter and a thread of comments.

The format is specified in dev/spec/issues.md. Reading is lenient, so any
Markdown file passes as an issue; writing always produces the strict format.
"""

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

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

FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)?---\n?", re.DOTALL)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
BY_RE = re.compile(r"^by:\s*(.*?)\s*$")
TITLE_RE = re.compile(r"^#\s+(.*?)\s*#*\s*$")


@dataclass
class Comment:
    text: str
    author: str | None = None


@dataclass
class Issue:
    title: str
    status: str = "backlog"
    description: str = ""
    comments: list[Comment] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    """Every frontmatter key but type and status, known or not."""

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_STATUSES


def slugify(title: str) -> str:
    """Turn a title into a file name stem: lowercase words joined by dashes."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return "-".join(words) or "issue"


def split_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Split text into its YAML frontmatter and the Markdown after it.

    Without a frontmatter, or with one that is not a YAML mapping, return
    None and the text untouched.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        loaded = yaml.safe_load(match.group(1) or "")
    except yaml.YAMLError:
        return None, text
    if not isinstance(loaded, dict):
        return None, text
    return {str(key): value for key, value in loaded.items()}, text[match.end() :]


def parse(text: str, slug: str = "") -> Issue:
    """Read an issue, accepting any Markdown text."""
    loaded, text = split_frontmatter(text)
    meta = loaded or {}
    broken = ""
    if loaded is None and (match := FRONTMATTER_RE.match(text)):
        # Keep a broken block as text, but never split it into comments.
        broken = match.group(0).rstrip("\n")
        text = text[match.end() :]
    meta.pop("type", None)
    status = str(meta.pop("status", None) or "backlog")

    first, *rest = _sections(text)
    title, description = _split_title(first)
    return Issue(
        title=title or slug.replace("-", " "),
        status=status,
        description="\n\n".join(part for part in (broken, description) if part),
        comments=[_comment(section) for section in rest],
        meta=meta,
    )


def load(path: Path) -> Issue:
    return parse(path.read_text(errors="replace"), path.stem)


def render(issue: Issue) -> str:
    """Write an issue in the strict format."""
    lines = ["---", "type: issue", f"status: {issue.status}"]
    for key, default in DEFAULTS.items():
        value = issue.meta.get(key, default)
        if value != default and value not in (None, "", []):
            lines.append(f"{key}: {_yaml_value(value)}")
    for key, value in issue.meta.items():
        if key not in DEFAULTS:
            lines.append(f"{key}: {_yaml_value(value)}")
    lines += ["---", "", f"# {issue.title}", ""]
    body = "\n".join(lines) + "\n"
    if issue.description:
        body += issue.description.strip("\n") + "\n"
    for comment in issue.comments:
        body += "\n---\n"
        if comment.author:
            body += f"by: {comment.author}\n"
        body += "\n" + comment.text.strip("\n") + "\n"
    return body


def new_issue(
    title: str,
    *,
    today: datetime.date | None = None,
    **meta: Any,
) -> Issue:
    """Create an issue in the backlog, dated today."""
    created = today or datetime.date.today()
    return Issue(title=title, meta={**meta, "created": created})


def _sections(text: str) -> list[str]:
    """Split the body on lines holding only ---, skipping fenced code."""
    sections: list[list[str]] = [[]]
    fence: str | None = None
    for line in text.splitlines():
        if match := FENCE_RE.match(line):
            if fence is None:
                fence = match.group(1)
            elif match.group(1) == fence:
                fence = None
        if fence is None and line.strip() == "---":
            sections.append([])
        else:
            sections[-1].append(line)
    return ["\n".join(lines).strip("\n") for lines in sections]


def _split_title(section: str) -> tuple[str, str]:
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if match := TITLE_RE.match(line):
            return match.group(1), "\n".join(lines[index + 1 :]).strip("\n")
        break
    return "", section


def _comment(section: str) -> Comment:
    first, _, rest = section.partition("\n")
    if match := BY_RE.match(first):
        return Comment(rest.strip("\n"), match.group(1) or None)
    return Comment(section)


def _yaml_value(value: Any) -> str:
    """Dump a value on one line, quoting only what YAML needs quoted."""
    dumped = yaml.safe_dump(value, default_flow_style=True, width=1 << 16)
    return dumped.removesuffix("...\n").strip()


def matches(issue: Issue, query: str, slug: str = "") -> bool:
    """Whether every word of query appears in the issue's title or metadata."""
    fields = [issue.title, slug, issue.status, *map(str, issue.meta.values())]
    haystack = " ".join(fields).lower()
    return all(word in haystack for word in query.lower().split())


def status_order(status: str) -> tuple[int, str]:
    """Sort key that puts known statuses in lifecycle order, others last."""
    return (STATUSES.index(status) if status in STATUSES else len(STATUSES), status)
