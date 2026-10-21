"""
Frontmatter of a report, and the fallback title of one that has none.

The YAML dialect matches the TypeScript original, which reads YAML 1.2: PyYAML
reads 1.1, where `yes`, `no`, `on` and `off` are booleans, `0123` is octal and
`2026-10-20` is a date. A title like `No` would become `False` and a commit
like `0123456` an octal number, so the loader below resolves booleans, integers
and floats as 1.2 does and leaves timestamps as strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from r2.core.reports.model import AgentContext, Diagnostic, Frontmatter

__all__ = ["ParsedDocument", "parse_document", "title_from_path"]

_KNOWN = frozenset({"title", "kind", "agent", "tags", "commit"})


def _construct_bool(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> bool:
    return str(loader.construct_scalar(node)).lower() == "true"


def _construct_int(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> int:
    text = str(loader.construct_scalar(node))
    if text[:2] == "0o":
        return int(text[2:], 8)
    return int(text, 16 if text[:2] == "0x" else 10)


def _construct_float(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> float:
    return float(str(loader.construct_scalar(node)).lower().replace(".inf", "inf"))


class _Loader(yaml.SafeLoader):
    """`SafeLoader` with the YAML 1.2 core schema for scalars."""


_Loader.yaml_implicit_resolvers = {
    char: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag
        not in {
            "tag:yaml.org,2002:bool",
            "tag:yaml.org,2002:int",
            "tag:yaml.org,2002:float",
            "tag:yaml.org,2002:timestamp",
        }
    ]
    for char, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    "tTfF",
)
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"),
    "-+0123456789",
)
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
        r"|[-+]?\.(?:inf|Inf|INF))$"
    ),
    "-+0123456789.",
)
_Loader.add_constructor("tag:yaml.org,2002:bool", _construct_bool)
_Loader.add_constructor("tag:yaml.org,2002:int", _construct_int)
_Loader.add_constructor("tag:yaml.org,2002:float", _construct_float)


@dataclass(frozen=True)
class ParsedDocument:
    """A report split into its frontmatter and its Markdown."""

    frontmatter: Frontmatter
    #: The document with any frontmatter removed.
    body: str
    #: 1-based source line the body starts on, so diagnostics can point at it.
    body_line: int
    diagnostics: list[Diagnostic] = field(default_factory=lambda: [])


@dataclass(frozen=True)
class _Split:
    yaml: str
    body: str
    body_line: int
    closed: bool


def parse_document(text: str) -> ParsedDocument:
    """
    Split frontmatter from body and read the fields this version knows.

    Never raises and never rejects a document. A file that is not valid Markdown
    does not exist, and frontmatter that is not valid YAML is a warning: the
    document still renders, because an agent that got the YAML wrong has usually
    written a perfectly good report under it.
    """
    split = _split_frontmatter(text)
    if split is None:
        return ParsedDocument(Frontmatter(), text, 1, [])

    if not split.closed:
        warning = _warning("frontmatter was never closed, treating the file as body")
        return ParsedDocument(Frontmatter(), text, 1, [warning])

    def result(
        frontmatter: Frontmatter, diagnostics: list[Diagnostic]
    ) -> ParsedDocument:
        return ParsedDocument(frontmatter, split.body, split.body_line, diagnostics)

    try:
        raw: Any = yaml.load(split.yaml, Loader=_Loader)
    except (yaml.YAMLError, ValueError, RecursionError) as error:
        warning = _warning(f"frontmatter is not valid YAML: {error}")
        return result(Frontmatter(), [warning])

    if raw is None:
        return result(Frontmatter(), [])
    if not isinstance(raw, dict):
        warning = _warning("frontmatter is not a mapping, ignoring it")
        return result(Frontmatter(), [warning])

    diagnostics: list[Diagnostic] = []
    return result(_read_fields(raw, diagnostics), diagnostics)  # pyright: ignore[reportUnknownArgumentType]


def title_from_path(path: str) -> str:
    """
    Fallback title, used when a report has neither a `title` field nor a heading.

    Deliberately not a Markdown operation: the renderer is the only Markdown
    parser in the project, and the heading fallback is resolved from its output.
    """
    base = path.rsplit("/", 1)[-1]
    words = re.sub(r"[-_]+", " ", base).strip()
    if words == "":
        return base
    return words[0].upper() + words[1:]


def _split_frontmatter(text: str) -> _Split | None:
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return None

    for index in range(1, len(lines)):
        if lines[index].rstrip() in ("---", "..."):
            return _Split(
                yaml="\n".join(lines[1:index]),
                body="\n".join(lines[index + 1 :]),
                body_line=index + 2,
                closed=True,
            )

    return _Split(yaml="", body=text, body_line=1, closed=False)


def _warning(message: str, field: str | None = None) -> Diagnostic:
    return Diagnostic(severity="warning", message=message, line=1, field=field)


def _read_fields(raw: dict[Any, Any], diagnostics: list[Diagnostic]) -> Frontmatter:
    frontmatter = Frontmatter()

    for key, value in raw.items():
        name = key if isinstance(key, str) else _scalar_text(key) or str(key)
        if name not in _KNOWN:
            frontmatter.extra[name] = value
            continue

        if name in ("title", "kind", "commit"):
            text = _scalar_text(value)
            if text is None:
                diagnostics.append(_wrong_type(name, "a string"))
            else:
                setattr(frontmatter, name, text)
        elif name == "tags":
            tags = _as_tags(value)
            if tags is None:
                diagnostics.append(_wrong_type(name, "a list of strings"))
            else:
                frontmatter.tags = tags
        else:
            agent = _as_agent(value)
            if agent is None:
                diagnostics.append(_wrong_type(name, "a mapping"))
            else:
                frontmatter.agent = agent

    return frontmatter


def _wrong_type(field: str, expected: str) -> Diagnostic:
    return _warning(f"{field} should be {expected}, ignoring it", field)


def _scalar_text(value: object) -> str | None:
    """A string, or a number or boolean written the way YAML writes it."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return None


def _as_tags(value: object) -> list[str] | None:
    """A single string is accepted for `tags`, because agents write it that way."""
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return None
    entries: list[object] = value  # pyright: ignore[reportUnknownVariableType]
    texts = (_scalar_text(entry) for entry in entries)
    return [text for text in texts if text is not None]


def _as_agent(value: object) -> AgentContext | None:
    """
    A bare string is the agent's name.

    `agent: Claude Opus 5` is what a writer reaches for first, and demanding a
    mapping for the common case is the kind of rule an agent in another
    repository will get wrong. Same leniency as `tags`, which takes one string
    for one tag.
    """
    name = _scalar_text(value)
    if name is not None:
        return AgentContext(name=name)
    if not isinstance(value, dict):
        return None
    raw: dict[object, object] = value  # pyright: ignore[reportUnknownVariableType]
    return AgentContext(
        name=_scalar_text(raw.get("name")),
        model=_scalar_text(raw.get("model")),
        session=_scalar_text(raw.get("session")),
    )
