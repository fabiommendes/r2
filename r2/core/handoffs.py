"""Handoffs: the state of an interrupted session, for another agent to resume.

The format is specified in dev/spec/handoffs.md. Handoffs live in
dev/handoffs of the main checkout, outside git. Reading is lenient; r2 only
ever rewrites the status line, so the rest of a handoff stays as written.
"""

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from r2.core import git, issues
from r2.core.files import atomic_write, locked, update
from r2.core.r2_context import find_root
from r2.core.threads import FRONTMATTER_RE, TITLE_RE, split_frontmatter

FOLDER = "dev/handoffs"
OPEN = "open"
TAKEN = "taken"
STATUSES = [OPEN, TAKEN]
PRUNE_DAYS = 7

STATUS_LINE_RE = re.compile(r"^status\s*:.*$", re.MULTILINE)
TYPE_LINE_RE = re.compile(r"^type\s*:.*\n", re.MULTILINE)


@dataclass
class Handoff:
    path: Path
    title: str
    status: str
    created: datetime.datetime
    """From the frontmatter or, when it has none, the modification time."""
    body: str
    meta: dict[str, Any] = field(default_factory=dict)
    """Every frontmatter key but type and status, known or not."""

    @property
    def id(self) -> str:
        return self.path.stem

    @property
    def issue(self) -> str | None:
        value = self.meta.get("issue")
        return str(value) if value else None


def folder(path: Path) -> Path:
    """The handoff folder of the project that contains path.

    It is always in the main checkout, even from another worktree: a new
    worktree does not see the ignored files of the others.
    """
    root = git.main_worktree(path) or find_root(path)
    return root / FOLDER


def project_root(handoffs: Path) -> Path:
    """The main checkout that holds the handoff folder."""
    return handoffs.parent.parent


def parse(text: str, path: Path, mtime: float = 0.0) -> Handoff:
    """Read a handoff, accepting any Markdown text."""
    meta, body = split_frontmatter(text)
    meta = meta or {}
    meta.pop("type", None)
    status = str(meta.pop("status", None) or OPEN)
    created = _datetime(meta.get("created"))
    if created is None:
        created = datetime.datetime.fromtimestamp(mtime)
    return Handoff(
        path=path,
        title=_title(body) or path.stem.replace("-", " "),
        status=status,
        created=created,
        body=body.strip("\n"),
        meta=meta,
    )


def load(path: Path) -> Handoff:
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse(text, path, path.stat().st_mtime)


def load_all(handoffs: Path) -> list[Handoff]:
    """Every handoff in the folder, the most recent first."""
    found = [load(path) for path in sorted(handoffs.glob("*.md"))]
    found.sort(key=lambda handoff: handoff.created, reverse=True)
    return found


def find(handoffs: Path, ident: str) -> Path:
    """
    The file of the handoff ident: a file stem or a unique prefix of one.

    Raise LookupError, saying why, when none or several match.
    """
    paths = sorted(handoffs.glob("*.md"))
    for path in paths:
        if path.stem == ident:
            return path
    found = [path for path in paths if path.stem.startswith(ident)]
    if len(found) == 1:
        return found[0]
    if not found:
        raise LookupError(f"no handoff matches {ident!r} in {handoffs}")
    names = ", ".join(path.stem for path in found)
    raise LookupError(f"{ident!r} matches several: {names}")


def latest_open(handoffs: Path) -> Path:
    """The open handoff created last. Raise LookupError when none is open."""
    for handoff in load_all(handoffs):
        if handoff.status == OPEN:
            return handoff.path
    raise LookupError(f"no open handoff in {handoffs}")


def set_status(text: str, status: str) -> str:
    """Rewrite the status line of the frontmatter, leaving the rest as is."""
    meta, _ = split_frontmatter(text)
    match = FRONTMATTER_RE.match(text)
    if meta is None or match is None or match.group(1) is None:
        return f"---\ntype: handoff\nstatus: {status}\n---\n\n{text}"
    block = match.group(1)
    line = f"status: {status}"
    if STATUS_LINE_RE.search(block):
        block = STATUS_LINE_RE.sub(line, block, count=1)
    elif type_line := TYPE_LINE_RE.search(block):
        block = block[: type_line.end()] + line + "\n" + block[type_line.end() :]
    else:
        block = line + "\n" + block
    return text[: match.start(1)] + block + text[match.end(1) :]


def take(path: Path) -> Handoff:
    """Mark the open handoff in path as taken, under the folder lock.

    Raise ValueError when it is not open, so two agents never resume the
    same handoff.
    """
    ignore(path.parent)

    def change(text: str) -> str:
        status = parse(text, path).status
        if status != OPEN:
            raise ValueError(f"handoff {path.stem} is {status}, not {OPEN}")
        return set_status(text, TAKEN)

    update(path, change)
    return load(path)


def stale(
    handoff: Handoff, now: datetime.datetime, days: int, root: Path
) -> str | None:
    """Why prune removes the handoff, or None to keep it."""
    if handoff.status == TAKEN:
        return TAKEN
    if now - handoff.created > datetime.timedelta(days=days):
        return f"older than {days} days"
    if handoff.issue is not None:
        issue = root / issues.FOLDER / f"{handoff.issue}.md"
        if issue.is_file() and not issues.load(issue).is_open:
            return f"issue {handoff.issue} is closed"
    return None


def prune(
    handoffs: Path,
    days: int = PRUNE_DAYS,
    now: datetime.datetime | None = None,
) -> list[tuple[Handoff, str]]:
    """Delete the taken handoffs, the old ones and those of closed issues.

    Return each deleted handoff with the reason.
    """
    if not handoffs.is_dir():
        return []
    ignore(handoffs)
    now = now or datetime.datetime.now()
    root = project_root(handoffs)
    removed = []
    with locked(handoffs):
        for handoff in load_all(handoffs):
            if (reason := stale(handoff, now, days, root)) is not None:
                handoff.path.unlink(missing_ok=True)
                removed.append((handoff, reason))
    return removed


def ignore(handoffs: Path) -> None:
    """Create the folder with a .gitignore holding *, if it has none."""
    handoffs.mkdir(parents=True, exist_ok=True)
    gitignore = handoffs / ".gitignore"
    if not gitignore.exists():
        atomic_write(gitignore, "*\n")


def _title(body: str) -> str:
    for line in body.splitlines():
        if line.strip():
            match = TITLE_RE.match(line)
            return match.group(1) if match else ""
    return ""


def _datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime.datetime):
        # Compare in local time, the time the skill writes.
        return value.astimezone().replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time())
    return None
