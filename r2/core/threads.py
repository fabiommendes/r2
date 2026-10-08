"""Threads: Markdown files with YAML frontmatter, a title and comments.

Issues and ADRs share this layout (see dev/spec/issues.md). A thread opens
with a frontmatter holding its type and status, then a level 1 heading with
the title and a description. Lines holding only --- start comments.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)?---\n?", re.DOTALL)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
BY_RE = re.compile(r"^by:\s*(.*?)\s*$")
TITLE_RE = re.compile(r"^#\s+(.*?)\s*#*\s*$")


@dataclass
class Comment:
    text: str
    author: str | None = None


@dataclass
class Thread:
    title: str
    status: str = ""
    description: str = ""
    comments: list[Comment] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    """Every frontmatter key but type and status, known or not."""


def _keep(threads: Mapping[str, Any]) -> None:
    pass


@dataclass(frozen=True)
class Format[T: Thread]:
    """What a kind of thread needs to be listed and edited in r2."""

    type: str
    """The type key in the frontmatter."""
    folder: str
    """Folder of the files, relative to the project root."""
    statuses: list[str]
    """Known statuses in lifecycle order."""
    closed: list[str]
    next_status: dict[str, str]
    """The status the next step of the workflow moves a thread to."""
    load: Callable[[Path], T]
    render: Callable[[T], str]
    set_status: Callable[[T, str], None]
    reconcile: Callable[[Mapping[str, T]], None] = _keep
    """Fix the statuses of threads read together, keyed by file stem."""

    def status_order(self, status: str) -> tuple[int, str]:
        return status_order(status, self.statuses)


def slugify(title: str, fallback: str) -> str:
    """Turn a title into a file name stem: lowercase words joined by dashes."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return "-".join(words) or fallback


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


def parse[T: Thread](text: str, cls: type[T], title: str, status: str) -> T:
    """Read a thread of class cls, accepting any Markdown text.

    title and status fill in what the text leaves out.
    """
    loaded, text = split_frontmatter(text)
    meta = loaded or {}
    broken = ""
    if loaded is None and (match := FRONTMATTER_RE.match(text)):
        # Keep a broken block as text, but never split it into comments.
        broken = match.group(0).rstrip("\n")
        text = text[match.end() :]
    meta.pop("type", None)

    first, *rest = _sections(text)
    heading, description = _split_title(first)
    return cls(
        title=heading or title,
        status=str(meta.pop("status", None) or status),
        description="\n\n".join(part for part in (broken, description) if part),
        comments=[_comment(section) for section in rest],
        meta=meta,
    )


def render(thread: Thread, type_: str, defaults: dict[str, Any]) -> str:
    """Write a thread in the strict format.

    defaults lists the known keys in writing order, with the value that
    leaves each one out. Unknown keys follow the known ones.
    """
    lines = ["---", f"type: {type_}", f"status: {thread.status}"]
    for key, default in defaults.items():
        value = thread.meta.get(key, default)
        if value != default and value not in (None, "", []):
            lines.append(f"{key}: {yaml_value(value)}")
    for key, value in thread.meta.items():
        if key not in defaults:
            lines.append(f"{key}: {yaml_value(value)}")
    lines += ["---", "", f"# {thread.title}", ""]
    body = "\n".join(lines) + "\n"
    if thread.description:
        body += thread.description.strip("\n") + "\n"
    for comment in thread.comments:
        body += "\n---\n"
        if comment.author:
            body += f"by: {comment.author}\n"
        body += "\n" + comment.text.strip("\n") + "\n"
    return body


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


def yaml_value(value: Any) -> str:
    """Dump a value on one line, quoting only what YAML needs quoted."""
    dumped = yaml.safe_dump(value, default_flow_style=True, width=1 << 16)
    return dumped.removesuffix("...\n").strip()


# Short names accepted in "key:value" filter words.
FILTER_ALIASES = {"tag": "tags", "related": "relatedto"}


def _words(value: Any) -> list[str]:
    if isinstance(value, list):
        return [word for item in value for word in _words(item)]
    return re.findall(r"[a-z0-9]+", str(value).lower())


def _starts_words(query: str, words: list[str]) -> bool:
    """Whether each word of query starts some word in words."""
    return all(any(w.startswith(q) for w in words) for q in _words(query))


def matches(thread: Thread, query: str, slug: str = "") -> bool:
    """Whether the thread passes the filter query.

    Each word of query must start a word of the title, the file name or the
    metadata. A "key:value" word looks in that key only, as in "tag:ui" or
    "kind:defect".
    """
    fields: dict[str, Any] = {
        "title": thread.title,
        "slug": slug,
        "status": thread.status,
        **{key.lower(): value for key, value in thread.meta.items()},
    }
    everything = _words(list(map(str, fields.values())))
    for token in query.lower().split():
        key, colon, value = token.partition(":")
        if colon and key and value:
            key = FILTER_ALIASES.get(key, key)
            if not _starts_words(value, _words(fields.get(key, ""))):
                return False
        elif not _starts_words(token, everything):
            return False
    return True


def comment_stub(author: str) -> str:
    """Text to append to a thread file to start a new comment."""
    return f"\n---\nby: {author}\n\n" if author else "\n---\n\n"


def append_stub(text: str, stub: str) -> str:
    """Append stub to the thread text, leaving one newline before it."""
    return text.rstrip("\n") + "\n" + stub


def status_order(status: str, statuses: list[str]) -> tuple[int, str]:
    """Sort key that puts known statuses in lifecycle order, others last."""
    index = statuses.index(status) if status in statuses else len(statuses)
    return (index, status)
