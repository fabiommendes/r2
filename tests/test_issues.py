import datetime

import yaml

from r2.core.issues import (
    Comment,
    Issue,
    append_stub,
    comment_stub,
    matches,
    new_issue,
    parse,
    render,
    set_status,
    slugify,
    status_order,
)

THREAD = """\
---
type: issue
status: todo
kind: defect
created: 2026-10-02
---

# The preview loses the cursor

Steps to reproduce.

```markdown
---
not a comment
```

---
by: fabio

It happens only with excerpts.

---

No author here.
"""


def test_parses_metadata_title_description_and_comments() -> None:
    issue = parse(THREAD)
    assert issue.status == "todo"
    assert issue.title == "The preview loses the cursor"
    assert issue.meta == {"kind": "defect", "created": datetime.date(2026, 10, 2)}
    assert "not a comment" in issue.description
    assert issue.comments == [
        Comment("It happens only with excerpts.", "fabio"),
        Comment("No author here."),
    ]


def test_render_round_trips_the_strict_format() -> None:
    assert render(parse(THREAD)) == THREAD


def test_reads_plain_markdown_leniently() -> None:
    issue = parse("Just some text.\n", "regex-corner-cases")
    assert issue.status == "backlog"
    assert issue.title == "regex corner cases"
    assert issue.description == "Just some text."
    assert issue.comments == []


def test_broken_frontmatter_stays_in_the_body() -> None:
    issue = parse("---\nstatus: [todo\n---\n\n# Title\n", "x")
    assert issue.status == "backlog"
    assert "status: [todo" in issue.description


def test_render_leaves_defaults_out_and_keeps_unknown_keys_last() -> None:
    issue = Issue(
        "Title",
        meta={
            "custom": "kept",
            "priority": "normal",
            "tags": [],
            "blocks": ["a", "b, c"],
            "milestone": "v1",
        },
    )
    head = render(issue).split("---\n")[1]
    assert head.splitlines() == [
        "type: issue",
        "status: backlog",
        "milestone: v1",
        "blocks: [a, 'b, c']",
        "custom: kept",
    ]
    assert yaml.safe_load(head)["blocks"] == ["a", "b, c"]


def test_new_issue_is_dated_and_in_the_backlog() -> None:
    issue = new_issue("Fix it", today=datetime.date(2026, 1, 2), kind="task")
    assert render(issue).startswith(
        "---\ntype: issue\nstatus: backlog\nkind: task\ncreated: 2026-01-02\n---\n"
    )


def test_slugify() -> None:
    assert slugify("The preview: loses the cursor!") == "the-preview-loses-the-cursor"
    assert slugify("???") == "issue"


def test_matches_the_start_of_words_in_title_slug_or_metadata() -> None:
    issue = Issue("Excerpt overflows", status="todo", meta={"tags": ["preview"]})
    assert matches(issue, "")
    assert matches(issue, "PREVIEW over")
    assert matches(issue, "todo", "excerpt-overflow")
    assert not matches(issue, "preview cursor")
    assert not matches(issue, "flows")


def test_matches_key_value_words_in_that_key_only() -> None:
    issue = Issue(
        "Build the UI",
        meta={"tags": ["ui"], "kind": "defect", "relatedTo": ["file-preview"]},
    )
    assert matches(issue, "tag:ui kind:def")
    assert matches(issue, "related:preview")
    assert not matches(issue, "tag:build")
    assert not matches(issue, "milestone:v1")


def test_status_order_follows_the_lifecycle_then_unknown_ones() -> None:
    statuses = ["active", "completed", "todo", "backlog"]
    assert sorted(statuses, key=status_order) == [
        "backlog",
        "todo",
        "completed",
        "active",
    ]


def test_appended_stub_parses_as_an_empty_comment_by_its_author() -> None:
    text = append_stub("# Title\n\nBody.\n\n", comment_stub("fabio"))
    assert text == "# Title\n\nBody.\n\n---\nby: fabio\n\n"
    assert parse(text).comments == [Comment("", "fabio")]


def test_set_status_dates_closing_and_clears_it_on_reopening() -> None:
    issue = Issue("X", status="todo")
    set_status(issue, "completed", datetime.date(2026, 1, 2))
    assert issue.meta["closed"] == datetime.date(2026, 1, 2)
    set_status(issue, "wont_fix", datetime.date(2026, 3, 4))
    assert issue.meta["closed"] == datetime.date(2026, 1, 2)
    set_status(issue, "todo")
    assert "closed" not in issue.meta
