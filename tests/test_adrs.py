import datetime
from pathlib import Path

from r2.core.adrs import (
    Adr,
    load,
    new_adr,
    next_stem,
    number,
    parse,
    render,
    set_status,
    status_order,
    supersede,
    superseded,
)

ADR = """\
---
type: adr
status: accepted
tags: [config]
created: 2026-10-07
decided: 2026-10-09
deciders: [fabio, claude]
supersedes: [0003-json-config]
---

# Store the configuration as TOML

## Context

JSON drops comments.

---
by: claude

TOML keeps comments.
"""


def test_render_round_trips_the_strict_format() -> None:
    adr = parse(ADR)
    assert adr.status == "accepted"
    assert adr.title == "Store the configuration as TOML"
    assert adr.meta["supersedes"] == ["0003-json-config"]
    assert render(adr) == ADR


def test_reads_plain_markdown_as_proposed_titled_by_the_stem() -> None:
    adr = parse("Some text.\n", "0007-use-yaml")
    assert adr.status == "proposed"
    assert adr.is_open
    assert adr.title == "use yaml"


def test_load_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "0002-keep-it.md"
    path.write_text(ADR)
    assert load(path).title == "Store the configuration as TOML"


def test_number_comes_from_the_stem_prefix() -> None:
    assert number("0012-toml-config") == 12
    assert number("toml-config") is None


def test_next_stem_follows_the_highest_number() -> None:
    stems = ["0001-a", "0009-b", "notes", "0003-c"]
    assert next_stem(stems, "Use TOML!") == "0010-use-toml"
    assert next_stem([], "???") == "0001-adr"


def test_new_adr_is_proposed_dated_and_has_the_madr_sections() -> None:
    text = render(new_adr("Use TOML", today=datetime.date(2026, 1, 2)))
    assert text == (
        "---\ntype: adr\nstatus: proposed\ncreated: 2026-01-02\n---\n\n"
        "# Use TOML\n\n## Context\n\n## Options\n\n## Decision\n\n"
        "## Consequences\n"
    )


def test_set_status_dates_the_decision_and_clears_it_on_reopening() -> None:
    adr = Adr("X")
    set_status(adr, "rejected", datetime.date(2026, 1, 2))
    assert adr.meta["decided"] == datetime.date(2026, 1, 2)
    set_status(adr, "accepted", datetime.date(2026, 3, 4))
    assert adr.meta["decided"] == datetime.date(2026, 1, 2)
    set_status(adr, "proposed")
    assert "decided" not in adr.meta


def test_supersede_writes_both_sides() -> None:
    old = Adr("Old", status="accepted", meta={"decided": datetime.date(2026, 1, 2)})
    new = Adr("New", status="accepted")
    supersede(new, "0005-new", old, "0002-old")
    supersede(new, "0005-new", old, "0002-old")
    assert new.meta["supersedes"] == ["0002-old"]
    assert old.status == "superseded"
    assert old.meta["supersededBy"] == "0005-new"
    assert old.meta["decided"] == datetime.date(2026, 1, 2)


def test_leaving_superseded_drops_the_pointer() -> None:
    adr = Adr("X", status="superseded", meta={"supersededBy": "0005-new"})
    set_status(adr, "accepted")
    assert "supersededBy" not in adr.meta


def test_superseded_trusts_supersedes_over_superseded_by() -> None:
    adrs = {
        "0001-old": Adr("Old", meta={"supersededBy": "0009-other"}),
        "0002-new": Adr("New", meta={"supersedes": ["0001-old", "0000-gone"]}),
    }
    assert superseded(adrs) == {"0001-old": "0002-new"}


def test_status_order_follows_the_lifecycle_then_unknown_ones() -> None:
    statuses = ["active", "superseded", "proposed", "accepted"]
    assert sorted(statuses, key=status_order) == [
        "proposed",
        "accepted",
        "superseded",
        "active",
    ]
