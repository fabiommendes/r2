from r2.core.reports.frontmatter import parse_document
from r2.core.reports.model import Frontmatter


def dump(frontmatter: Frontmatter) -> dict[str, object]:
    return frontmatter.model_dump(exclude_none=True, by_alias=True)


def test_reads_a_report_with_no_frontmatter() -> None:
    d = parse_document("# Hello\n\nbody")
    assert dump(d.frontmatter) == {"extra": {}}
    assert d.body == "# Hello\n\nbody"
    assert d.body_line == 1
    assert d.diagnostics == []


def test_reads_the_known_fields() -> None:
    d = parse_document(
        "\n".join(
            [
                "---",
                "title: Auth flow review",
                "kind: review",
                "tags: [security, auth]",
                "commit: a1b2c3d",
                "agent:",
                "  name: claude",
                "  session: 83a595e6",
                "---",
                "body",
            ]
        )
    )
    assert d.frontmatter.title == "Auth flow review"
    assert d.frontmatter.kind == "review"
    assert d.frontmatter.tags == ["security", "auth"]
    assert d.frontmatter.commit == "a1b2c3d"
    assert d.frontmatter.agent is not None
    assert d.frontmatter.agent.model_dump(exclude_none=True) == {
        "name": "claude",
        "session": "83a595e6",
    }
    assert d.body == "body"
    assert d.body_line == 10
    assert d.diagnostics == []


def test_preserves_unknown_fields() -> None:
    d = parse_document("---\ntitle: x\nfuture: 42\n---\n")
    assert d.frontmatter.extra == {"future": 42}
    assert d.diagnostics == []


def test_accepts_a_single_tag_as_a_string() -> None:
    d = parse_document("---\ntags: auth\n---\n")
    assert d.frontmatter.tags == ["auth"]


def test_accepts_a_bare_string_as_the_agent_name() -> None:
    d = parse_document("---\nagent: Claude Opus 5\n---\n\nbody\n")
    assert d.frontmatter.agent is not None
    assert d.frontmatter.agent.model_dump(exclude_none=True) == {
        "name": "Claude Opus 5"
    }
    assert d.diagnostics == []


def test_warns_and_keeps_the_body_when_the_yaml_is_broken() -> None:
    d = parse_document('---\ntitle: "unterminated\n---\nbody here')
    assert d.diagnostics[0].severity == "warning"
    assert d.body == "body here"
    assert d.frontmatter.title is None


def test_warns_and_keeps_everything_when_the_fence_is_never_closed() -> None:
    text = "---\ntitle: x\n\nstill writing"
    d = parse_document(text)
    assert "never closed" in d.diagnostics[0].message
    assert d.body == text


def test_warns_on_a_field_of_the_wrong_type_without_losing_the_rest() -> None:
    d = parse_document("---\ntitle: [a, b]\nkind: review\n---\n")
    assert d.frontmatter.kind == "review"
    assert d.frontmatter.title is None
    assert d.diagnostics[0].field == "title"


def test_ignores_frontmatter_that_is_not_a_mapping() -> None:
    d = parse_document("---\n- a\n- b\n---\nbody")
    assert "not a mapping" in d.diagnostics[0].message
    assert d.body == "body"


def test_treats_a_bare_rule_inside_the_body_as_a_thematic_break() -> None:
    d = parse_document("before\n\n---\n\nafter")
    assert dump(d.frontmatter) == {"extra": {}}
    assert d.body == "before\n\n---\n\nafter"


def test_accepts_an_empty_frontmatter_block() -> None:
    d = parse_document("---\n---\nbody")
    assert dump(d.frontmatter) == {"extra": {}}
    assert d.body == "body"
    assert d.diagnostics == []


def test_reads_yaml_as_1_2_not_1_1() -> None:
    d = parse_document(
        "---\ntitle: No\ncommit: 0123456\nkind: 2026-10-20\nflag: yes\n---\n"
    )
    assert d.frontmatter.title == "No"
    assert d.frontmatter.commit == "123456"  # decimal, not octal
    assert d.frontmatter.kind == "2026-10-20"
    assert d.frontmatter.extra == {"flag": "yes"}
    assert d.diagnostics == []


def test_writes_booleans_the_way_yaml_does() -> None:
    d = parse_document("---\ntitle: true\n---\n")
    assert d.frontmatter.title == "true"
