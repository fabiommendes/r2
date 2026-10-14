"""
The user story file of one role, `docs/user-stories/<role>.md`:

```markdown
---
type: stories
status: active
role: student
---

# Student user stories

What the role is and what it may do.

## Joining the platform

### Log in

    status: implemented
    url: /login

The narrative: what the user wants, does and ends up with.
```

A story is identified by `<role>: <slug of the title>`. Reading accepts any
Markdown text; writing always produces the format above.
"""

from __future__ import annotations

import re
import textwrap
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import yaml

from r2.core.threads import FENCE_RE, split_frontmatter, yaml_value

__all__ = [
    "KNOWN_STATUSES",
    "Section",
    "Story",
    "StoryFile",
    "is_strict",
    "parse",
    "parse_id",
    "slugify",
    "story_id",
]

TYPE = "stories"
TODO = "todo"
PARTIAL = "partial"
IMPLEMENTED = "implemented"
DEPRECATED = "deprecated"
KNOWN_STATUSES = (TODO, PARTIAL, IMPLEMENTED, DEPRECATED)
"""Story statuses r2 writes. Other values are kept and count as partial."""

META_KEYS = ("status", "url", "relatedTo")
"""Metadata keys in writing order; unknown keys follow, as written."""

ID_RE = re.compile(r"^\s*([^:\s]+)\s*:\s*(.+?)\s*$")


def slugify(title: str) -> str:
    """
    Lowercase ASCII words of title, joined by dashes. Accents are dropped,
    so "Configuração" becomes "configuracao".
    """
    ascii_title = (
        unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    )
    return "-".join(re.findall(r"[a-z0-9]+", ascii_title.lower()))


def story_id(role: str, title: str) -> str:
    """The id of the story of role with title: `role: slug`."""
    return f"{role}: {slugify(title)}"


def parse_id(text: str) -> tuple[str, str] | None:
    """
    The role and slug of `role: title`, or `role: slug`; None when text has
    no role. The title is slugified, so a test title or a story title gives
    the same id.
    """
    match = ID_RE.match(text)
    if match is None:
        return None
    slug = slugify(match.group(2))
    return (match.group(1), slug) if slug else None


@dataclass
class Story:
    title: str
    narrative: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    """The metadata block, as written; status included."""

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def status(self) -> str:
        """The status as written; `todo` when there is none."""
        value = self.meta.get("status")
        return str(value) if value not in (None, "") else TODO

    @property
    def needs_test(self) -> bool:
        """
        Whether the story must have a test: it is implemented or partial. An
        unknown status, such as `web`, counts as partial.
        """
        return self.status not in (TODO, DEPRECATED)

    def to_markdown(self) -> str:
        """The story as a level 3 section, without a trailing newline."""
        parts = [f"### {self.title}"]
        meta = _ordered({"status": self.status, **self.meta})
        parts.append("\n".join(f"    {key}: {yaml_value(v)}" for key, v in meta))
        if self.narrative:
            parts.append(self.narrative)
        return "\n\n".join(parts)


@dataclass
class Section:
    name: str
    """The level 2 heading; empty for stories before the first one."""
    intro: str = ""
    stories: list[Story] = field(default_factory=list)


@dataclass
class StoryFile:
    role: str
    title: str = ""
    intro: str = ""
    sections: list[Section] = field(default_factory=list)
    status: str = "active"
    meta: dict[str, Any] = field(default_factory=dict)
    """Frontmatter keys other than type, status and role."""

    @property
    def stories(self) -> list[Story]:
        return [story for section in self.sections for story in section.stories]

    def find(self, slug: str) -> Story | None:
        """The first story whose title slugifies to slug."""
        return next((s for s in self.stories if s.slug == slug), None)

    def section_of(self, story: Story) -> Section:
        return next(s for s in self.sections if any(x is story for x in s.stories))

    def section(self, name: str) -> Section:
        """The section called name, case-insensitively, added at the end if new."""
        found = next(
            (s for s in self.sections if s.name.lower() == name.strip().lower()), None
        )
        if found is None:
            found = Section(name.strip())
            self.sections.append(found)
        return found

    def remove(self, story: Story) -> None:
        section = self.section_of(story)
        section.stories = [s for s in section.stories if s is not story]

    def to_markdown(self) -> str:
        """The file in the strict format. It round-trips through `parse`."""
        lines = ["---", f"type: {TYPE}", f"status: {self.status}"]
        lines.append(f"role: {yaml_value(self.role)}")
        lines += [f"{key}: {yaml_value(value)}" for key, value in self.meta.items()]
        lines += ["---", "", f"# {self.title or default_title(self.role)}", ""]
        if self.intro:
            lines += [self.intro, ""]
        for section in self.sections:
            if section.name:
                lines += [f"## {section.name}", ""]
            if section.intro:
                lines += [section.intro, ""]
            for story in section.stories:
                lines += [story.to_markdown(), ""]
        return "\n".join(lines)


def default_title(role: str) -> str:
    return f"{role[:1].upper()}{role[1:]} user stories"


def is_strict(src: str) -> bool:
    """Whether the text declares itself a story file in its frontmatter."""
    meta, _ = split_frontmatter(src)
    return meta is not None and meta.get("type") == TYPE


def parse(src: str, role: str) -> StoryFile:
    """
    Read a story file, accepting any Markdown text. role is used when the
    frontmatter has none; callers pass the file name without `.md`.
    """
    loaded, body = split_frontmatter(src)
    meta = dict(loaded or {})
    meta.pop("type", None)
    status = str(meta.pop("status", None) or "active")
    role = str(meta.pop("role", None) or role)

    head, sections = _split(body)
    title, head = _split_title(head)
    return StoryFile(
        role=role,
        title=title or default_title(role),
        intro=_text(head),
        sections=sections,
        status=status,
        meta=meta,
    )


def _split(body: str) -> tuple[list[str], list[Section]]:
    """The lines before the first level 2 or 3 heading, and the sections."""
    # (heading level, heading text, lines under it); level 0 is the head.
    blocks: list[tuple[int, str, list[str]]] = [(0, "", [])]
    fence: str | None = None
    for line in body.splitlines():
        if match := FENCE_RE.match(line):
            if fence is None:
                fence = match.group(1)
            elif match.group(1) == fence:
                fence = None
        if fence is None and line.startswith("## "):
            blocks.append((2, line[3:].strip(), []))
        elif fence is None and line.startswith("### "):
            blocks.append((3, line[4:].strip(), []))
        else:
            blocks[-1][2].append(line)

    sections: list[Section] = []
    for level, heading, lines in blocks[1:]:
        if level == 2:
            sections.append(Section(heading, _text(lines)))
            continue
        if not sections:
            sections.append(Section(""))
        meta, narrative = _story_body(lines)
        sections[-1].stories.append(Story(heading, narrative, meta))
    return blocks[0][2], sections


def _story_body(lines: list[str]) -> tuple[dict[str, Any], str]:
    """The metadata block and the narrative of a story."""
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].strip() and _indented(lines[end]):
        end += 1
    if end > start:
        try:
            loaded = yaml.safe_load(textwrap.dedent("\n".join(lines[start:end])))
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict) and loaded:
            meta = {str(key): value for key, value in loaded.items()}
            return meta, _text(lines[end:])
    return {}, _text(lines)


def _indented(line: str) -> bool:
    return line.startswith(("    ", "\t"))


def _split_title(lines: list[str]) -> tuple[str, list[str]]:
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            return line[2:].strip(), lines[index + 1 :]
        break
    return "", lines


def _text(lines: list[str]) -> str:
    """The lines as one text, without blank runs or surrounding blank lines."""
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")


def _ordered(meta: dict[str, Any]) -> list[tuple[str, Any]]:
    known = [(key, meta[key]) for key in META_KEYS if key in meta]
    rest = [(key, value) for key, value in meta.items() if key not in META_KEYS]
    return [(key, value) for key, value in known + rest if value not in (None, "", [])]
