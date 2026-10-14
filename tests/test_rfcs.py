import datetime
from pathlib import Path

from r2.core.rfcs import (
    FORMAT,
    Rfc,
    load,
    new_path,
    new_rfc,
    parse,
    render,
    set_status,
    status_order,
)

RFC = """\
---
type: rfc
status: accepted
tags: [layout]
relatedTo: [dev/adr/0003-layout.md]
created: 2026-10-07
decided: 2026-10-09
creator: claude
---

# One layout for every repository

## Problem

Each tool has its own layout.

## Outcome

- dev/adr/0003-layout.md

---
by: fabio

Accepted.
"""


def test_render_round_trips_the_strict_format() -> None:
    rfc = parse(RFC)
    assert rfc.status == "accepted"
    assert not rfc.is_open
    assert rfc.title == "One layout for every repository"
    assert rfc.meta["relatedTo"] == ["dev/adr/0003-layout.md"]
    assert [c.author for c in rfc.comments] == ["fabio"]
    assert render(rfc) == RFC


def test_reads_plain_markdown_as_a_draft_titled_by_the_slug() -> None:
    rfc = parse("Some text.\n", "one-layout")
    assert rfc.status == "draft"
    assert rfc.is_open
    assert rfc.title == "one layout"


def test_load_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "layout.md"
    path.write_text(RFC)
    assert load(path).title == "One layout for every repository"


def test_new_rfc_is_a_dated_draft_with_the_sections() -> None:
    text = render(new_rfc("One layout", today=datetime.date(2026, 1, 2)))
    assert text == (
        "---\ntype: rfc\nstatus: draft\ncreated: 2026-01-02\n---\n\n"
        "# One layout\n\n## Problem\n\n## Proposal\n\n## Alternatives\n\n"
        "## Open questions\n\n## Outcome\n"
    )


def test_new_path_is_a_free_slug_without_a_number(tmp_path: Path) -> None:
    assert new_path(tmp_path, "One layout!") == tmp_path / "one-layout.md"
    (tmp_path / "one-layout.md").write_text("")
    assert new_path(tmp_path, "One layout") == tmp_path / "one-layout-2.md"
    assert new_path(tmp_path, "???") == tmp_path / "rfc.md"


def test_set_status_dates_the_decision_and_clears_it_on_reopening() -> None:
    rfc = Rfc("X")
    set_status(rfc, "withdrawn", datetime.date(2026, 1, 2))
    assert rfc.meta["decided"] == datetime.date(2026, 1, 2)
    set_status(rfc, "rejected", datetime.date(2026, 3, 4))
    assert rfc.meta["decided"] == datetime.date(2026, 1, 2)
    set_status(rfc, "draft")
    assert "decided" not in rfc.meta


def test_draft_is_the_only_open_status() -> None:
    assert FORMAT.closed == ["accepted", "rejected", "withdrawn"]
    assert FORMAT.next_status["draft"] == "accepted"


def test_status_order_follows_the_lifecycle_then_unknown_ones() -> None:
    statuses = ["active", "withdrawn", "draft", "accepted"]
    assert sorted(statuses, key=status_order) == [
        "draft",
        "accepted",
        "withdrawn",
        "active",
    ]
