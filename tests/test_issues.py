import datetime

import yaml

from robin.issues import Comment, Issue, new_issue, parse, render, slugify

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
