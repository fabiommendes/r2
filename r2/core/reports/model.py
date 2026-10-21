"""
Types for the `.reportlab/` contract and the document AST.

These models are the single source of truth for the report format: the web
API serves them as they are, and the browser's TypeScript types are generated
from the OpenAPI schema they produce. Field names go on the wire in camelCase.

An optional field is absent from the wire, never `null`: `Wire` drops `null`
from the schema of every field that defaults to `None`, and the API
serializes with `exclude_none`.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

__all__ = [
    "SEVERITIES",
    "AgentContext",
    "Blockquote",
    "BlockError",
    "BlockTag",
    "Break",
    "Candidate",
    "CandidateNode",
    "Code",
    "DataTable",
    "Diagnostic",
    "DocNode",
    "Emphasis",
    "FileFact",
    "Finding",
    "FindingMark",
    "FindingState",
    "Frontmatter",
    "Heading",
    "Image",
    "Inline",
    "InlineCode",
    "Link",
    "ListNode",
    "Paragraph",
    "Ref",
    "RefLink",
    "RenderedReport",
    "Resolutions",
    "ReviewMarks",
    "Severity",
    "Strong",
    "Table",
    "Text",
    "ThematicBreak",
    "UnknownBlock",
    "Wire",
]


def _drop_null(schema: dict[str, Any]) -> None:
    """
    Make every nullable property optional and not nullable, since `None` is
    never sent. Every other property is required, defaults included,
    because the server always sends it.
    """
    required: list[str] = schema.get("required", [])
    for name, prop in schema.get("properties", {}).items():
        options = [item for item in prop.get("anyOf", ()) if item != {"type": "null"}]
        if len(options) == len(prop.get("anyOf", ())):
            continue
        if name in required:
            required.remove(name)
        del prop["anyOf"]
        if len(options) == 1:
            prop.update(options[0])
        else:
            prop["anyOf"] = options
        if prop.get("default", ...) is None:
            del prop["default"]


class Wire(BaseModel):
    """Base of every model that crosses the API."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        json_schema_serialization_defaults_required=True,
        json_schema_extra=_drop_null,
    )


#: Only affects the icon and the grouping in the navigator. A kind outside
#: this list is accepted and rendered generically.
type ReportKind = Literal["review", "analysis", "plan", "summary", "benchmark", "note"]

type Severity = Literal["high", "medium", "low", "info"]
type FindingState = Literal["seen", "accepted", "rejected"]

#: From most to least severe.
SEVERITIES: tuple[Severity, ...] = ("high", "medium", "low", "info")


class AgentContext(Wire):
    name: str | None = None
    model: str | None = None
    session: str | None = None


class Frontmatter(Wire):
    """
    Every field is optional, including all of them. A file with no
    frontmatter is a valid report: the cheapest thing an agent can do is
    write Markdown to a path, and nothing in this format should make it
    hesitate.
    """

    title: str | None = None
    kind: str | None = None
    agent: AgentContext | None = None
    tags: list[str] | None = None
    #: Provenance only. Refs resolve against the working tree, never this.
    commit: str | None = None
    #: Unknown fields, kept verbatim for forward compatibility.
    extra: dict[str, Any] = Field(default_factory=dict)


class Ref(Wire):
    """
    A pointer into the repository, resolved against the working tree. Lines
    are 1-based and inclusive.
    """

    path: str
    start: int | None = None
    end: int | None = None
    #: Column from the `path:5:10` form. Carried faithfully, not used yet.
    column: int | None = None


class BlockTag(Wire):
    #: The part after `rl:`, for example `finding`.
    type: str
    attrs: dict[str, str] = Field(default_factory=dict)


class Diagnostic(Wire):
    severity: Literal["error", "warning"]
    message: str
    line: int | None = None
    field: str | None = None


class FindingMark(Wire):
    state: FindingState
    note: str | None = None


class ReviewMarks(Wire):
    """`<name>.review.json`, beside the report. Deleted with it."""

    read: str | None = None
    findings: dict[str, FindingMark] = Field(default_factory=dict)


class Candidate(Wire):
    """Something in prose that looks like a reference. See `candidates`."""

    #: `stem` comes only from a code span: the file stem of an issue, an ADR
    #: or an RFC.
    kind: Literal["path", "commit", "stem"]
    #: Exactly the source text matched, so a caller can splice it out.
    raw: str
    #: Offsets into the string that was scanned.
    start: int
    end: int
    #: For `path`: the ref, already split into path and line range. For
    #: `stem`: the stem.
    path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    column: int | None = None


#
# Inline nodes
#
class Text(Wire):
    type: Literal["text"] = "text"
    value: str


class Break(Wire):
    type: Literal["break"] = "break"


class Emphasis(Wire):
    type: Literal["emphasis"] = "emphasis"
    children: list[Inline]


class Strong(Wire):
    type: Literal["strong"] = "strong"
    children: list[Inline]


class InlineCode(Wire):
    type: Literal["inlineCode"] = "inlineCode"
    value: str
    #: What the span may name, when it is a path or a stem. A link only once
    #: resolved.
    candidate: Candidate | None = None


class Link(Wire):
    type: Literal["link"] = "link"
    url: str
    children: list[Inline]


class Image(Wire):
    type: Literal["image"] = "image"
    url: str
    alt: str


class RefLink(Wire):
    """An explicit `rl:` link, or a ref attribute. Always a link."""

    type: Literal["refLink"] = "refLink"
    ref: Ref
    children: list[Inline]


class CandidateNode(Wire):
    """Something that looks like a reference. A link only once resolved."""

    type: Literal["candidate"] = "candidate"
    candidate: Candidate


type Inline = Annotated[
    Text
    | Break
    | Emphasis
    | Strong
    | InlineCode
    | Link
    | Image
    | RefLink
    | CandidateNode,
    Field(discriminator="type"),
]


#
# Block nodes
#
class Heading(Wire):
    type: Literal["heading"] = "heading"
    depth: Literal[1, 2, 3, 4, 5, 6]
    children: list[Inline]


class Paragraph(Wire):
    type: Literal["paragraph"] = "paragraph"
    children: list[Inline]


class ListNode(Wire):
    type: Literal["list"] = "list"
    ordered: bool
    items: list[list[DocNode]]


class Blockquote(Wire):
    type: Literal["blockquote"] = "blockquote"
    children: list[DocNode]


class Code(Wire):
    type: Literal["code"] = "code"
    lang: str | None = None
    value: str
    open: bool | None = None


class Table(Wire):
    type: Literal["table"] = "table"
    head: list[list[Inline]]
    rows: list[list[list[Inline]]]


class ThematicBreak(Wire):
    type: Literal["thematicBreak"] = "thematicBreak"


class Finding(Wire):
    """One `rl:finding`. `id` is positional (`f1`, `f2`) and keys the marks."""

    type: Literal["finding"] = "finding"
    id: str
    severity: Severity
    title: str
    ref: Ref | None = None
    children: list[DocNode]
    #: The fence was never closed: the agent is still writing this.
    open: bool | None = None


type Cell = str | int | float | bool | None


class DataTable(Wire):
    type: Literal["dataTable"] = "dataTable"
    caption: str | None = None
    columns: list[str]
    rows: list[list[Cell]]
    open: bool | None = None


class UnknownBlock(Wire):
    """An `rl:` block this version does not know. Rendered as code."""

    type: Literal["unknownBlock"] = "unknownBlock"
    tag: str
    value: str
    open: bool | None = None


class BlockError(Wire):
    """A malformed block, rendered in place so the rest of the report survives."""

    type: Literal["error"] = "error"
    message: str
    line: int | None = None
    #: The block's raw body, so nothing an agent wrote is thrown away.
    value: str | None = None


type DocNode = Annotated[
    Heading
    | Paragraph
    | ListNode
    | Blockquote
    | Code
    | Table
    | ThematicBreak
    | Finding
    | DataTable
    | UnknownBlock
    | BlockError,
    Field(discriminator="type"),
]


class RenderedReport(Wire):
    nodes: list[DocNode]
    #: Text of the first heading, used to title a report that has no `title`.
    first_heading: str | None = None
    #: Some block has no closing fence: the agent is probably still writing.
    open: bool | None = None
    #: Explicit refs, in document order. Drives the file list of a report.
    refs: list[Ref] = Field(default_factory=list)
    #: Detected references, deduplicated, awaiting resolution.
    candidates: list[Candidate] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class FileFact(Wire):
    """One file that a report cites, as it is on disk right now."""

    #: Project-relative path, normalized.
    path: str
    #: ISO 8601 modification time.
    modified: str
    #: Modified after the report was written: the cited lines may have moved.
    changed: bool | None = None


#: What the server sends after checking references against the working tree,
#: keyed by the path as the document carries it. A path with no entry is not
#: a file on disk and renders as plain text, never as a broken link.
type Resolutions = dict[str, FileFact]
