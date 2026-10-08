from pathlib import Path

from r2.core.history import History, Location
from r2.core.links import Link

DOCS = Location("docs", Link(Path("a.md")))
ISSUES = Location("issues", Link(Path("b.md")))
LIVE = Location("live")


def test_a_new_history_goes_nowhere() -> None:
    history = History()
    assert history.current is None
    assert not history.can_go_back
    assert not history.can_go_forward
    assert history.back() is None
    assert history.forward() is None


def test_back_and_forward_walk_the_visits() -> None:
    history = History()
    for location in (DOCS, ISSUES, LIVE):
        history.visit(location)
    assert history.back() == ISSUES
    assert history.back() == DOCS
    assert history.back() is None
    assert history.forward() == ISSUES
    assert history.forward() == LIVE
    assert history.forward() is None
    assert history.current == LIVE


def test_visiting_the_current_location_changes_nothing() -> None:
    history = History()
    history.visit(DOCS)
    history.visit(Location("docs", Link(Path("a.md"))))
    assert not history.can_go_back


def test_a_visit_after_going_back_clears_forward() -> None:
    history = History()
    for location in (DOCS, ISSUES):
        history.visit(location)
    history.back()
    history.visit(LIVE)
    assert not history.can_go_forward
    assert history.back() == DOCS


def test_the_oldest_entries_are_dropped_over_the_limit() -> None:
    history = History(limit=2)
    for location in (DOCS, ISSUES, LIVE):
        history.visit(location)
    assert history.back() == ISSUES
    assert history.back() is None
