import json
from typing import Any

import pytest

from r2.core.reports.model import (
    CandidateNode,
    DocNode,
    Finding,
    Inline,
    RefLink,
)
from r2.core.reports.render import create_parser, render_markdown


def dump(node: Any) -> Any:
    return node.model_dump(exclude_none=True, by_alias=True)


def first(md: str) -> DocNode:
    return render_markdown(md).nodes[0]


def inlines(md: str) -> list[Inline]:
    node = first(md)
    assert node.type == "paragraph", f"expected paragraph, got {node.type}"
    return node.children


def types(nodes: list[Any]) -> list[str]:
    return [node.type for node in nodes]


class TestBlockStructure:
    def test_parses_headings_and_records_the_first_one(self) -> None:
        r = render_markdown("# Auth review\n\ntext\n\n## Details\n")
        assert r.first_heading == "Auth review"
        assert types(r.nodes) == ["heading", "paragraph", "heading"]

    def test_parses_a_list_of_paragraphs(self) -> None:
        node = first("- one\n- two\n")
        assert node.type == "list"
        assert len(node.items) == 2

    def test_parses_a_blockquote(self) -> None:
        node = first("> quoted\n")
        assert node.type == "blockquote"
        assert node.children[0].type == "paragraph"

    def test_parses_a_gfm_table(self) -> None:
        node = first("| a | b |\n| - | - |\n| 1 | 2 |\n")
        assert node.type == "table"
        assert len(node.head) == 2
        assert len(node.rows) == 1

    def test_keeps_an_ordinary_fence_as_code_with_its_language(self) -> None:
        node = first("```python\nx = 1\n```\n")
        assert dump(node) == {"type": "code", "lang": "python", "value": "x = 1\n"}

    def test_parses_a_thematic_break(self) -> None:
        assert dump(first("***\n")) == {"type": "thematicBreak"}


class TestUntrustedInput:
    def test_never_produces_a_node_carrying_markup(self) -> None:
        r = render_markdown("<script>alert(1)</script>\n\n<b>bold</b>\n")
        text = json.dumps([dump(n) for n in r.nodes])
        assert "script" in text
        for node in r.nodes:
            assert node.type in ("paragraph", "code")

    def test_parser_has_raw_html_off(self) -> None:
        assert create_parser().options["html"] is False


class TestRlBlocks:
    finding_source = "\n".join(
        [
            "```rl:finding severity=high ref=src/auth/session.py:40-58",
            "The token is not rotated on login.",
            "```",
            "",
        ]
    )

    def test_parses_a_finding(self) -> None:
        r = render_markdown(self.finding_source)
        f = r.nodes[0]
        assert isinstance(f, Finding)
        assert f.id == "f1"
        assert f.severity == "high"
        assert dump(f.ref) == {"path": "src/auth/session.py", "start": 40, "end": 58}
        assert f.title == "The token is not rotated on login."
        assert f.children[0].type == "paragraph"
        assert f.open is None
        assert len(r.findings) == 1
        assert [dump(ref) for ref in r.refs] == [
            {"path": "src/auth/session.py", "start": 40, "end": 58}
        ]

    def test_collects_what_a_finding_body_cites(self) -> None:
        r = render_markdown(
            "```rl:finding severity=low ref=src/a.ts:1\n"
            "Also in src/b.ts:3 and [here](rl:src/c.ts).\n```\n"
        )
        assert [ref.path for ref in r.refs] == ["src/a.ts", "src/c.ts"]
        assert [c.path for c in r.candidates] == ["src/b.ts"]

    def test_numbers_findings_in_document_order(self) -> None:
        r = render_markdown(f"{self.finding_source}\n{self.finding_source}")
        assert [f.id for f in r.findings] == ["f1", "f2"]

    def test_defaults_a_missing_severity_to_info_and_warns(self) -> None:
        r = render_markdown("```rl:finding\nsomething\n```\n")
        f = r.nodes[0]
        assert isinstance(f, Finding)
        assert f.severity == "info"
        assert r.diagnostics[0].field == "severity"

    def test_warns_on_an_unknown_severity(self) -> None:
        r = render_markdown("```rl:finding severity=critical\nx\n```\n")
        f = r.nodes[0]
        assert isinstance(f, Finding)
        assert f.severity == "info"
        assert "critical" in r.diagnostics[0].message

    def test_reports_a_bad_ref_without_losing_the_finding(self) -> None:
        r = render_markdown("```rl:finding severity=low ref=../../etc/passwd\nx\n```\n")
        f = r.nodes[0]
        assert isinstance(f, Finding)
        assert f.ref is None
        assert r.diagnostics[0].severity == "error"
        assert r.diagnostics[0].line == 1

    def test_parses_a_data_table(self) -> None:
        node = first(
            '```rl:table caption="Latency"\n[{"a": 1, "b": "x"}, {"a": 2}]\n```\n'
        )
        assert dump(node) == {
            "type": "dataTable",
            "caption": "Latency",
            "columns": ["a", "b"],
            "rows": [[1, "x"], [2, None]],
        }

    def test_keeps_the_body_when_a_table_is_not_valid_json(self) -> None:
        node = first("```rl:table\nnot json\n```\n")
        assert node.type == "error"
        assert node.value == "not json\n"
        assert "not valid JSON" in node.message

    def test_rejects_json_constants_that_javascript_does_not_read(self) -> None:
        assert first('```rl:table\n[{"a": NaN}]\n```\n').type == "error"

    def test_renders_an_unknown_block_as_itself(self) -> None:
        node = first("```rl:flamegraph sample=42\ndata\n```\n")
        assert dump(node) == {
            "type": "unknownBlock",
            "tag": "flamegraph",
            "value": "data\n",
        }

    def test_reports_a_malformed_tag_in_place(self) -> None:
        r = render_markdown("```rl:Finding\nx\n```\n")
        assert dump(r.nodes[0]) == {
            "type": "error",
            "message": "malformed block tag: rl:Finding",
            "value": "x\n",
        }
        assert r.diagnostics[0].severity == "error"


class TestReportBeingWritten:
    def test_marks_an_unterminated_fence_as_open(self) -> None:
        node = first("```rl:finding severity=high\nstill typing")
        assert isinstance(node, Finding)
        assert node.open is True

    def test_marks_an_unterminated_plain_fence_as_open(self) -> None:
        node = first("```python\nx = 1")
        assert node.type == "code"
        assert node.open is True

    def test_flags_the_report_as_open(self) -> None:
        assert render_markdown("```python\nx = 1").open is True
        assert render_markdown("```python\nx = 1\n```\n").open is None

    def test_renders_every_prefix_of_a_report_without_raising(self) -> None:
        source = "\n".join(
            [
                "---",
                "title: Live",
                "---",
                "",
                "# Heading",
                "",
                "Text about src/a.ts:4 and more.",
                "",
                "```rl:finding severity=high ref=src/a.ts:4",
                "Body of the finding.",
                "```",
                "",
                "| a | b |",
                "| - | - |",
                "| 1 | 2 |",
            ]
        )
        for i in range(len(source) + 1):
            render_markdown(source[:i])


class TestInlineContent:
    def test_detects_a_path_in_prose(self) -> None:
        parts = inlines("look at src/a.ts:42 now")
        assert types(parts) == ["text", "candidate", "text"]
        part = parts[1]
        assert isinstance(part, CandidateNode)
        assert part.candidate.path == "src/a.ts"

    def test_a_code_span_naming_a_path_or_stem_is_a_candidate(self) -> None:
        r = render_markdown("Run `src/a.py:3`, see `issue-flow`, not `x = 1`.\n")
        assert [(c.kind, c.path) for c in r.candidates] == [
            ("path", "src/a.py"),
            ("stem", "issue-flow"),
        ]
        codes = [
            n for n in inlines("`src/a.py:3` and `x = 1`") if n.type == "inlineCode"
        ]
        assert [n.candidate is not None for n in codes] == [True, False]

    def test_keeps_a_path_inside_inline_code_as_code(self) -> None:
        parts = inlines("the file `src/a.ts` is fine")
        assert not any(p.type == "candidate" for p in parts)

    def test_does_not_linkify_a_path_whose_extension_is_a_top_level_domain(
        self,
    ) -> None:
        parts = inlines("rewrite main.rs today")
        assert not any(p.type == "link" for p in parts)
        part = parts[1]
        assert isinstance(part, CandidateNode)
        assert part.candidate.path == "main.rs"

    def test_still_linkifies_a_real_url_and_does_not_treat_it_as_a_path(
        self,
    ) -> None:
        parts = inlines("see https://example.com/a/b.html for more")
        assert any(p.type == "link" for p in parts)
        assert not any(p.type == "candidate" for p in parts)

    def test_does_not_linkify_a_bare_email(self) -> None:
        parts = inlines("mail someone@example.com now")
        assert types(parts) == ["text"]

    def test_turns_an_rl_link_into_a_ref_link(self) -> None:
        r = render_markdown("Rotation in [`session.py`](rl:src/auth/session.py:40-58).")
        node = r.nodes[0]
        assert node.type == "paragraph"
        link = next(c for c in node.children if isinstance(c, RefLink))
        assert link.ref.start == 40
        assert len(r.refs) == 1

    def test_reads_the_older_locator_form_in_an_rl_link(self) -> None:
        r = render_markdown("Rotation in [`session.py`](rl:src/a.ts#L40-58).")
        assert dump(r.refs[0]) == {"path": "src/a.ts", "start": 40, "end": 58}

    def test_degrades_an_invalid_rl_link_to_text(self) -> None:
        r = render_markdown("see [bad](rl:/etc/passwd)")
        node = r.nodes[0]
        assert node.type == "paragraph"
        assert not any(c.type == "refLink" for c in node.children)
        assert r.diagnostics[0].severity == "error"

    def test_parses_emphasis_strong_and_their_nesting(self) -> None:
        parts = inlines("**bold *and italic***")
        strong = next(p for p in parts if p.type == "strong")
        assert any(c.type == "emphasis" for c in strong.children)

    def test_deduplicates_candidates_and_refs(self) -> None:
        r = render_markdown("src/a.ts and src/a.ts again")
        assert len(r.candidates) == 1

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("a\nb", ["text", "text", "text"]),
            ("a  \nb", ["text", "break", "text"]),
        ],
    )
    def test_breaks(self, source: str, expected: list[str]) -> None:
        assert types(inlines(source)) == expected
