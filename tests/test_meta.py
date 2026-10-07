import datetime

from r2.core.issues import split_frontmatter
from r2.tui.widgets.meta import STATUS_COLORS, render_meta

COLORS = {name: "#808080" for name in [*STATUS_COLORS.values(), "secondary"]}


def test_split_frontmatter() -> None:
    assert split_frontmatter("---\na: 1\n---\n# T\n") == ({"a": 1}, "# T\n")
    assert split_frontmatter("# T\n") == (None, "# T\n")
    assert split_frontmatter("---\n[x\n---\n") == (None, "---\n[x\n---\n")


def test_render_meta_shows_one_key_per_line_and_skips_normal_values() -> None:
    meta = {
        "type": "issue",
        "status": "in_progress",
        "priority": "normal",
        "kind": "defect",
        "created": datetime.date(2026, 10, 2),
        "empty": [],
    }
    lines = render_meta(meta, COLORS).plain.splitlines()
    assert lines[0] == "type     issue"
    assert lines[1].startswith("status    in progress")
    assert lines[2:] == ["kind     defect", "created  2026-10-02"]


def test_lists_of_scalars_join_with_a_dim_separator() -> None:
    text = render_meta({"tags": ["a", "b", 3]}, COLORS)
    assert text.plain == "tags  a; b; 3"
    dim = [
        text.plain[span.start : span.end] for span in text.spans if span.style == "dim"
    ]
    assert dim == ["tags  ", "; ", "; "]


def test_nested_values_show_as_yaml_under_the_key() -> None:
    meta = {"id": "x", "owner": {"name": "ana", "teams": ["a", "b"]}}
    assert render_meta(meta, COLORS).plain.splitlines() == [
        "id     x",
        "owner  ",
        "       name: ana",
        "       teams:",
        "       - a",
        "       - b",
    ]
