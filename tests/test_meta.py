import datetime

from robin.issues import split_frontmatter
from robin.widgets.meta import STATUS_COLORS, render_meta

COLORS = {name: "#808080" for name in [*STATUS_COLORS.values(), "secondary"]}


def test_split_frontmatter() -> None:
    assert split_frontmatter("---\na: 1\n---\n# T\n") == ({"a": 1}, "# T\n")
    assert split_frontmatter("# T\n") == (None, "# T\n")
    assert split_frontmatter("---\n[x\n---\n") == (None, "---\n[x\n---\n")


def test_render_meta_skips_normal_values_and_groups_links() -> None:
    meta = {
        "type": "issue",
        "status": "in_progress",
        "priority": "normal",
        "kind": "defect",
        "created": datetime.date(2026, 10, 2),
        "tags": ["a", "b"],
        "relatedTo": ["x"],
    }
    lines = render_meta(meta, COLORS).plain.splitlines()
    assert "in progress" in lines[0] and lines[0].endswith("issue")
    assert lines[1] == "kind defect  created 2026-10-02"
    assert lines[2] == "#a #b  → x"
