import datetime
from pathlib import Path

from r2.core.issues import split_frontmatter
from r2.tui.views.issues import STATUS_COLORS, issue_fields
from r2.tui.widgets.meta import render_meta

COLORS = {
    name: "#808080" for name in [*STATUS_COLORS.values(), "secondary", "text-accent"]
}


def test_split_frontmatter() -> None:
    assert split_frontmatter("---\na: 1\n---\n# T\n") == ({"a": 1}, "# T\n")
    assert split_frontmatter("# T\n") == (None, "# T\n")
    assert split_frontmatter("---\n[x\n---\n") == (None, "---\n[x\n---\n")


def test_render_meta_shows_one_key_per_line_and_skips_empty_values() -> None:
    meta: dict[str, object] = {
        "type": "note",
        "priority": "normal",
        "empty": [],
        "none": None,
    }
    assert render_meta(meta, COLORS).plain.splitlines() == [
        "type      note",
        "priority  normal",
    ]


def test_issue_fields_pill_the_status_and_skip_normal_values() -> None:
    meta = {
        "type": "issue",
        "status": "in_progress",
        "priority": "normal",
        "kind": "defect",
        "created": datetime.date(2026, 10, 2),
        "empty": [],
    }
    lines = render_meta(meta, COLORS, issue_fields(lambda: None)).plain.splitlines()
    assert lines[0] == "type     issue"
    assert lines[1] == "status   \ue0b6in progress\ue0b4"
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


def test_related_entries_link_to_existing_files_only(tmp_path: Path) -> None:
    (tmp_path / "dev" / "issues").mkdir(parents=True)
    (tmp_path / "dev" / "issues" / "old-issue.md").write_text("")
    (tmp_path / "spec.md").write_text("")
    meta = {"relatedTo": ["old-issue", "gone", "spec.md"]}
    text = render_meta(meta, COLORS, issue_fields(lambda: tmp_path))
    assert text.plain == "relatedTo  old-issue ↗; gone; spec.md ↗"
    clicks = [
        span.style.meta["@click"]
        for span in text.spans
        if not isinstance(span.style, str) and "@click" in span.style.meta
    ]
    assert clicks == [
        "field('relatedTo', 'old-issue')",
        "field('relatedTo', 'spec.md')",
    ]
