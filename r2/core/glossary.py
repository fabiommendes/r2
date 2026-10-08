"""
Glossary: the project's ubiquitous language, kept in one Markdown file.

The format is specified in dev/spec/glossary.md:

```markdown
---
type: glossary
status: active
---

# Glossary

Introduction.

---

## Term

Definition.

- tags: process
- avoid: synonym, other synonym
- related: Other term
- code: `module.Class`
- pt: termo
```

Reading is lenient, so any Markdown text passes as a glossary; writing always
produces the strict format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from r2.core.threads import FENCE_RE, split_frontmatter, yaml_value

__all__ = ["Glossary", "Term", "parse"]

DEFAULT_TITLE = "Glossary"

# Fields in writing order; language codes come after them, then the rest.
FIELDS = ["tags", "avoid", "related", "code"]

FIELD_RE = re.compile(r"^- ([a-z][a-z0-9_-]*):[ \t]*(.*?)\s*$")
LANGUAGE_RE = re.compile(r"[a-z]{2}")


@dataclass
class Term:
    name: str
    definition: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    """Values of the trailing field list, by key, as written."""

    def items(self, key: str) -> list[str]:
        """The comma separated entries of a field."""
        return [
            item.strip() for item in self.fields.get(key, "").split(",") if item.strip()
        ]

    @property
    def tags(self) -> list[str]:
        return self.items("tags")

    @property
    def avoid(self) -> list[str]:
        return self.items("avoid")

    @property
    def related(self) -> list[str]:
        return self.items("related")

    @property
    def languages(self) -> dict[str, str]:
        """The term in other languages, by ISO 639-1 code."""
        return {key: value for key, value in self.fields.items() if _is_language(key)}

    def to_markdown(self) -> str:
        """The term as a level 2 section, without a trailing newline."""
        parts = [f"## {self.name}"]
        if self.definition:
            parts.append(self.definition)
        fields = [f"- {key}: {value}" for key, value in _ordered(self.fields) if value]
        if fields:
            parts.append("\n".join(fields))
        return "\n\n".join(parts)


@dataclass
class Glossary:
    terms: list[Term]
    intro: str
    title: str = DEFAULT_TITLE
    status: str = "active"
    meta: dict[str, Any] = field(default_factory=dict)
    """Frontmatter keys other than type and status."""

    def sorted(self) -> Glossary:
        """
        Sort the glossary terms alphabetically by name.
        """
        return Glossary(
            terms=sorted(self.terms, key=lambda term: term.name.lower()),
            intro=self.intro,
            title=self.title,
            status=self.status,
            meta=self.meta,
        )

    def find(self, name: str) -> Term | None:
        """The term called name, compared case-insensitively."""
        target = name.strip().lower()
        return next((term for term in self.terms if term.name.lower() == target), None)

    def tags(self) -> list[str]:
        """Every tag in use, sorted; tags that differ only in case are one."""
        seen: dict[str, str] = {}
        for term in self.terms:
            for tag in term.tags:
                seen.setdefault(tag.lower(), tag)
        return [seen[key] for key in sorted(seen)]

    def render(self) -> str:
        """
        Render the glossary as plain text: the intro, then "name: definition".
        """
        output = [self.intro, ""]
        for term in self.terms:
            output.append(f"{term.name}: {term.definition}")
        return "\n".join(output)

    def to_markdown(self) -> str:
        """
        Render the glossary back as a markdown document.

        The result round-trips through :func:`parse`.
        """
        lines = ["---", "type: glossary", f"status: {self.status}"]
        lines += [f"{key}: {yaml_value(value)}" for key, value in self.meta.items()]
        lines += ["---", "", f"# {self.title}", ""]
        if self.intro:
            lines += [self.intro, ""]
        lines += ["---", ""]
        for term in self.terms:
            lines += [term.to_markdown(), ""]
        return "\n".join(lines)


def parse(src: str) -> Glossary:
    """
    Read a glossary, accepting any Markdown text.
    """
    loaded, body = split_frontmatter(src)
    meta = dict(loaded or {})
    meta.pop("type", None)
    status = str(meta.pop("status", None) or "active")

    head, sections = _split_terms(body)
    title, head = _split_title(head)
    intro = _intro(head)
    terms = [_term(section) for section in sections]
    return Glossary(terms=terms, intro=intro, title=title, status=status, meta=meta)


def _split_terms(body: str) -> tuple[list[str], list[list[str]]]:
    """Split the body into the lines before the first term and each term."""
    head: list[str] = []
    sections: list[list[str]] = []
    fence: str | None = None
    for line in body.splitlines():
        if match := FENCE_RE.match(line):
            if fence is None:
                fence = match.group(1)
            elif match.group(1) == fence:
                fence = None
        if fence is None and line.startswith("## "):
            sections.append([line])
        elif sections:
            sections[-1].append(line)
        else:
            head.append(line)
    return head, sections


def _split_title(lines: list[str]) -> tuple[str, list[str]]:
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            return line[2:].strip(), lines[index + 1 :]
        break
    return DEFAULT_TITLE, lines


def _intro(lines: list[str]) -> str:
    """The text before the first term, without the --- lines that end it."""
    kept = [line for line in lines if line.strip() != "---"]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip("\n")


def _term(lines: list[str]) -> Term:
    name = lines[0][3:].strip()
    body = "\n".join(lines[1:]).strip("\n")
    blocks = re.split(r"\n[ \t]*\n", body) if body else []
    fields: dict[str, str] = {}
    if blocks:
        matches = [FIELD_RE.match(line) for line in blocks[-1].splitlines()]
        if all(matches):
            fields = {m.group(1): m.group(2) for m in matches if m}
            blocks = blocks[:-1]
    definition = "\n\n".join(blocks).strip("\n")
    return Term(name=name, definition=definition, fields=fields)


def _is_language(key: str) -> bool:
    return key not in FIELDS and LANGUAGE_RE.fullmatch(key) is not None


def _ordered(fields: dict[str, str]) -> list[tuple[str, str]]:
    known = [(key, fields[key]) for key in FIELDS if key in fields]
    languages = sorted((k, v) for k, v in fields.items() if _is_language(k))
    rest = [
        (k, v) for k, v in fields.items() if k not in FIELDS and not _is_language(k)
    ]
    return known + languages + rest
