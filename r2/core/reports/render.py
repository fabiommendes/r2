"""
Markdown to a typed document AST.

The parser is `markdown-it-py`, used for its token stream rather than its HTML
renderer: the UI mounts interactive components for `rl:` blocks, and a report is
untrusted input (dev/adr/0006-markdown-with-typed-blocks.md,
dev/adr/0009-markdown-it-and-detected-references.md). No node here carries raw
HTML, which is the "strip, do not sanitize and keep" rule expressed in the
type system, and `MARKDOWN_IT_OPTIONS` turns raw HTML off at the parser so it
never reaches a token in the first place.

Both extensions happen while walking the token stream rather than as
markdown-it plugins, because nothing here goes through its renderer: `rl:`
fences become `Finding` and `DataTable` nodes, and text tokens are split on
detected references (see `candidates`).
"""

from __future__ import annotations

import json
from typing import Any, Literal

from markdown_it import MarkdownIt
from markdown_it.token import Token

from r2.core.reports.blocks import BlockTagError, parse_block_tag
from r2.core.reports.candidates import candidate_key, detect_candidates
from r2.core.reports.model import (
    SEVERITIES,
    BlockError,
    Blockquote,
    Break,
    Candidate,
    CandidateNode,
    Cell,
    Code,
    DataTable,
    Diagnostic,
    DocNode,
    Emphasis,
    Finding,
    Heading,
    Image,
    Inline,
    InlineCode,
    Link,
    ListNode,
    Paragraph,
    Ref,
    RefLink,
    RenderedReport,
    Severity,
    Strong,
    Table,
    Text,
    ThematicBreak,
    UnknownBlock,
)
from r2.core.reports.refs import RefError, format_ref, parse_ref

__all__ = ["MARKDOWN_IT_OPTIONS", "create_parser", "render_markdown"]

#: The parser configuration is part of the contract, not a preference.
#: `html: False` is a security boundary: with it, raw HTML in a report is
#: escaped by the parser and cannot reach the document tree.
MARKDOWN_IT_OPTIONS: dict[str, Any] = {
    "html": False,
    "linkify": True,
    "typographer": False,
    "breaks": False,
}

_CLOSERS = frozenset(
    {
        "heading_close",
        "paragraph_close",
        "blockquote_close",
        "bullet_list_close",
        "ordered_list_close",
        "list_item_close",
        "table_close",
        "thead_close",
        "tbody_close",
        "tr_close",
        "th_close",
        "td_close",
    }
)

type _Depth = Literal[1, 2, 3, 4, 5, 6]

_DEPTHS: dict[str, _Depth] = {
    "h1": 1,
    "h2": 2,
    "h3": 3,
    "h4": 4,
    "h5": 5,
    "h6": 6,
}


def create_parser() -> MarkdownIt:
    """
    Build the parser, with the same rules as `markdown-it` in JavaScript.

    `js-default` is the preset that matches it: markdown-it-py's own `default`
    is CommonMark, without tables or strikethrough.

    `fuzzy_link` is off for a reason that is not obvious: `.rs`, `.sh`, `.io`,
    `.dev`, `.me` and `.co` are real top-level domains as well as common file
    extensions, so linkify would turn `main.rs` into a link to a website. With
    it off, only a URL carrying a scheme becomes a link, and paths stay as text
    where candidate detection can see them.
    """
    md = MarkdownIt("js-default", MARKDOWN_IT_OPTIONS)
    assert md.linkify is not None  # linkify-it-py is a dependency
    md.linkify.set({"fuzzy_link": False, "fuzzy_email": False})
    return md


_shared: MarkdownIt | None = None


def render_markdown(body: str) -> RenderedReport:
    """Render a Markdown body, as far as it goes if it is incomplete."""
    global _shared
    if _shared is None:
        _shared = create_parser()
    tokens = _shared.parse(body)
    return _Transformer(body.split("\n")).run(tokens)


class _Transformer:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._tokens: list[Token] = []
        self._at = 0
        self._refs: list[Ref] = []
        self._candidates: list[Candidate] = []
        self._findings: list[Finding] = []
        self._diagnostics: list[Diagnostic] = []
        self._seen_candidates: set[str] = set()
        self._seen_refs: set[str] = set()
        self._first_heading: str | None = None
        self._saw_open = False

    def run(self, tokens: list[Token]) -> RenderedReport:
        self._tokens = tokens
        self._at = 0
        nodes = self._blocks()
        return RenderedReport(
            nodes=nodes,
            first_heading=self._first_heading,
            open=True if self._saw_open else None,
            refs=self._refs,
            candidates=self._candidates,
            findings=self._findings,
            diagnostics=self._diagnostics,
        )

    def _blocks(self) -> list[DocNode]:
        """Consume tokens until a closing token or the end of the stream."""
        nodes: list[DocNode] = []
        while self._at < len(self._tokens):
            token = self._tokens[self._at]
            if token.type in _CLOSERS:
                break
            node = self._block(token)
            if node is not None:
                nodes.append(node)
        return nodes

    def _block(self, token: Token) -> DocNode | None:
        match token.type:
            case "heading_open":
                return self._heading(token)
            case "paragraph_open":
                return self._paragraph()
            case "blockquote_open":
                return self._blockquote()
            case "bullet_list_open" | "ordered_list_open":
                return self._list(ordered=token.type == "ordered_list_open")
            case "table_open":
                return self._table()
            case "fence":
                self._at += 1
                return self._fence(token)
            case "code_block":
                self._at += 1
                return Code(value=token.content)
            case "hr":
                self._at += 1
                return ThematicBreak()
            case "html_block":
                # Unreachable while `html` is off, and harmless if that ever
                # changes: the markup is shown as text, never mounted.
                self._at += 1
                return Code(value=token.content)
            case _:
                self._at += 1
                return None

    def _heading(self, token: Token) -> DocNode:
        self._at += 1
        children = self._inline_run()
        self._expect("heading_close")
        if self._first_heading is None:
            self._first_heading = _plain_text(children).strip() or None
        return Heading(depth=_DEPTHS.get(token.tag, 6), children=children)

    def _paragraph(self) -> DocNode:
        self._at += 1
        children = self._inline_run()
        self._expect("paragraph_close")
        return Paragraph(children=children)

    def _blockquote(self) -> DocNode:
        self._at += 1
        children = self._blocks()
        self._expect("blockquote_close")
        return Blockquote(children=children)

    def _list(self, *, ordered: bool) -> DocNode:
        self._at += 1
        items: list[list[DocNode]] = []
        while (
            self._at < len(self._tokens)
            and self._tokens[self._at].type == "list_item_open"
        ):
            self._at += 1
            items.append(self._blocks())
            self._expect("list_item_close")
        self._expect("ordered_list_close" if ordered else "bullet_list_close")
        return ListNode(ordered=ordered, items=items)

    def _table(self) -> DocNode:
        self._at += 1
        head: list[list[Inline]] = []
        rows: list[list[list[Inline]]] = []

        while self._at < len(self._tokens):
            kind = self._tokens[self._at].type
            if kind == "table_close":
                break
            if kind == "thead_open":
                self._at += 1
                parsed = self._table_rows()
                head = parsed[0] if parsed else []
                self._expect("thead_close")
            elif kind == "tbody_open":
                self._at += 1
                rows.extend(self._table_rows())
                self._expect("tbody_close")
            else:
                self._at += 1
        self._expect("table_close")
        return Table(head=head, rows=rows)

    def _table_rows(self) -> list[list[list[Inline]]]:
        rows: list[list[list[Inline]]] = []
        while self._at < len(self._tokens) and self._tokens[self._at].type == "tr_open":
            self._at += 1
            cells: list[list[Inline]] = []
            while self._at < len(self._tokens):
                opener = self._tokens[self._at].type
                if opener not in ("th_open", "td_open"):
                    break
                self._at += 1
                cells.append(self._inline_run())
                self._expect("th_close" if opener == "th_open" else "td_close")
            self._expect("tr_close")
            rows.append(cells)
        return rows

    def _fence(self, token: Token) -> DocNode:
        open_ = self._is_unterminated(token)
        if open_:
            self._saw_open = True

        try:
            tag = parse_block_tag(token.info)
        except BlockTagError as error:
            message = str(error)
            self._diagnostics.append(
                _with_line(Diagnostic(severity="error", message=message), token)
            )
            return BlockError(message=message, value=token.content)

        if tag is None:
            words = token.info.split()
            return Code(
                lang=words[0] if words else None,
                value=token.content,
                open=True if open_ else None,
            )

        match tag.type:
            case "finding":
                return self._finding(tag.attrs, token, open_)
            case "table":
                return self._data_table(tag.attrs, token, open_)
            case _:
                return UnknownBlock(
                    tag=tag.type,
                    value=token.content,
                    open=True if open_ else None,
                )

    def _finding(self, attrs: dict[str, str], token: Token, open_: bool) -> Finding:
        body = token.content
        inner = render_markdown(body)
        finding = Finding(
            id=f"f{len(self._findings) + 1}",
            severity=self._severity(attrs.get("severity"), token),
            title=attrs.get("title", "").strip() or _first_line(body) or "Finding",
            children=inner.nodes,
            open=True if open_ else None,
        )

        raw = attrs.get("ref", "")
        if raw != "":
            try:
                ref = parse_ref(raw)
            except RefError as error:
                diagnostic = Diagnostic(severity="error", message=str(error))
                self._diagnostics.append(_with_line(diagnostic, token))
            else:
                finding.ref = ref
                self._collect_ref(ref)

        # The body is a document of its own, but what it cites is cited by the
        # report: without this, a path in a finding never resolves to a link.
        for ref in inner.refs:
            self._collect_ref(ref)
        for candidate in inner.candidates:
            self._collect_candidate(candidate)
        self._findings.append(finding)
        return finding

    def _severity(self, raw: str | None, token: Token) -> Severity:
        if raw is None:
            message = "finding has no severity, treating it as info"
        else:
            value = raw.strip().lower()
            for severity in SEVERITIES:
                if severity == value:
                    return severity
            message = f"unknown severity {raw}, treating it as info"
        diagnostic = Diagnostic(severity="warning", message=message, field="severity")
        self._diagnostics.append(_with_line(diagnostic, token))
        return "info"

    def _data_table(self, attrs: dict[str, str], token: Token, open_: bool) -> DocNode:
        try:
            raw: Any = json.loads(token.content, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as error:
            return self._table_error(f"rl:table body is not valid JSON: {error}", token)

        if not isinstance(raw, list):
            return self._table_error(
                "rl:table body must be a JSON array of objects", token
            )

        columns: list[str] = []
        objects: list[dict[str, Any]] = []
        for entry in raw:  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(entry, dict):
                continue
            row: dict[str, Any] = entry  # pyright: ignore[reportUnknownVariableType]
            objects.append(row)
            for key in row:
                if key not in columns:
                    columns.append(key)

        return DataTable(
            caption=attrs.get("caption", "").strip() or None,
            columns=columns,
            rows=[[_cell(row.get(key)) for key in columns] for row in objects],
            open=True if open_ else None,
        )

    def _table_error(self, message: str, token: Token) -> BlockError:
        diagnostic = Diagnostic(severity="warning", message=message)
        self._diagnostics.append(_with_line(diagnostic, token))
        return BlockError(message=message, value=token.content)

    def _inline_run(self) -> list[Inline]:
        if self._at >= len(self._tokens) or self._tokens[self._at].type != "inline":
            return []
        token = self._tokens[self._at]
        self._at += 1
        return self._inlines(token.children or [])

    def _inlines(self, tokens: list[Token]) -> list[Inline]:
        out: list[Inline] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            i += 1
            match token.type:
                case "text":
                    out.extend(self._text(token.content))
                case "code_inline":
                    out.append(InlineCode(value=token.content))
                case "softbreak":
                    out.append(Text(value=" "))
                case "hardbreak":
                    out.append(Break())
                case "image":
                    out.append(Image(url=_attr(token, "src"), alt=token.content))
                case "strong_open":
                    inner, i = _nested(tokens, i, "strong_close")
                    out.append(Strong(children=self._inlines(inner)))
                case "em_open":
                    inner, i = _nested(tokens, i, "em_close")
                    out.append(Emphasis(children=self._inlines(inner)))
                case "link_open":
                    inner, i = _nested(tokens, i, "link_close")
                    out.append(self._link(_attr(token, "href"), self._inlines(inner)))
                case "html_inline":
                    out.append(Text(value=token.content))
                case _:
                    pass
        return out

    def _link(self, href: str, children: list[Inline]) -> Inline:
        if not href.startswith("rl:"):
            return Link(url=href, children=children)
        try:
            ref = parse_ref(href[3:])
        except RefError as error:
            self._diagnostics.append(Diagnostic(severity="error", message=str(error)))
            return Text(value=_plain_text(children))
        self._collect_ref(ref)
        return RefLink(ref=ref, children=children)

    def _text(self, value: str) -> list[Inline]:
        found = detect_candidates(value)
        if not found:
            return [Text(value=value)]

        out: list[Inline] = []
        cursor = 0
        for candidate in found:
            if candidate.start > cursor:
                out.append(Text(value=value[cursor : candidate.start]))
            self._collect_candidate(candidate)
            out.append(CandidateNode(candidate=candidate))
            cursor = candidate.end
        if cursor < len(value):
            out.append(Text(value=value[cursor:]))
        return out

    def _collect_ref(self, ref: Ref) -> None:
        key = format_ref(ref)
        if key not in self._seen_refs:
            self._seen_refs.add(key)
            self._refs.append(ref)

    def _collect_candidate(self, candidate: Candidate) -> None:
        key = candidate_key(candidate)
        if key not in self._seen_candidates:
            self._seen_candidates.add(key)
            self._candidates.append(candidate)

    def _is_unterminated(self, token: Token) -> bool:
        """
        True when the fence has no closing marker, which is the normal state of
        a report an agent is still writing.
        """
        if token.map is None:
            return False
        end = token.map[1]
        if not 1 <= end <= len(self._lines):
            return True
        return not self._lines[end - 1].lstrip().startswith(token.markup)

    def _expect(self, kind: str) -> None:
        if self._at < len(self._tokens) and self._tokens[self._at].type == kind:
            self._at += 1


def _attr(token: Token, name: str) -> str:
    """markdown-it allows numeric attribute values; the AST wants strings."""
    value = token.attrGet(name)
    return "" if value is None else str(value)


def _nested(tokens: list[Token], start: int, closer: str) -> tuple[list[Token], int]:
    """
    The tokens between an opener and its matching `closer`, and the index after
    the closer. `start` is the index just after the opener.
    """
    inner: list[Token] = []
    depth = 0
    for i in range(start, len(tokens)):
        token = tokens[i]
        if token.type == closer and depth == 0:
            return inner, i + 1
        depth += token.nesting
        inner.append(token)
    return inner, len(tokens)


def _plain_text(inlines: list[Inline]) -> str:
    out = ""
    for node in inlines:
        match node:
            case Text() | InlineCode():
                out += node.value
            case CandidateNode():
                out += node.candidate.raw
            case Break():
                out += " "
            case Image():
                out += node.alt
            case Emphasis() | Strong() | Link() | RefLink():
                out += _plain_text(node.children)
    return out


def _first_line(text: str) -> str:
    return text.split("\n")[0].strip()


def _cell(value: Any) -> Cell:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _reject_constant(name: str) -> Any:
    """JSON has no `NaN` or `Infinity`, though Python's parser reads them."""
    raise ValueError(f"unexpected constant {name}")


def _with_line(diagnostic: Diagnostic, token: Token) -> Diagnostic:
    if token.map is None:
        return diagnostic
    return diagnostic.model_copy(update={"line": token.map[0] + 1})
