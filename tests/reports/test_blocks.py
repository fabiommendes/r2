import pytest

from r2.core.reports.blocks import BlockTagError, parse_block_tag


def test_ignores_fences_that_are_not_rl_blocks() -> None:
    assert parse_block_tag("python") is None
    assert parse_block_tag("") is None


def test_parses_a_type_with_no_attributes() -> None:
    tag = parse_block_tag("rl:table")
    assert tag is not None
    assert tag.model_dump() == {"type": "table", "attrs": {}}


def test_parses_bare_and_quoted_attributes() -> None:
    tag = parse_block_tag("rl:finding severity=high ref=src/a.py#L4-8")
    assert tag is not None
    assert tag.model_dump() == {
        "type": "finding",
        "attrs": {"severity": "high", "ref": "src/a.py#L4-8"},
    }

    quoted = parse_block_tag('rl:table caption="Latency by endpoint"')
    assert quoted is not None
    assert quoted.attrs["caption"] == "Latency by endpoint"


def test_accepts_an_unknown_type_for_forward_compatibility() -> None:
    tag = parse_block_tag("rl:flamegraph sample=42")
    assert tag is not None
    assert tag.type == "flamegraph"


@pytest.mark.parametrize("info", ["rl:", "rl:Finding"])
def test_rejects_a_malformed_tag(info: str) -> None:
    with pytest.raises(BlockTagError, match="malformed block tag"):
        parse_block_tag(info)
