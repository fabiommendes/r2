"""
Tests for r2.core.coverage.analysis, on hand built maps.

Spans are written in text form. Line spans (`f.py:N:0-N:0`) are abbreviated
with `line("f.py", N)`.
"""

from __future__ import annotations

import pytest

from r2.core.coverage.analysis import (
    Minimized,
    Suite,
    TestRef,
    added,
    adds,
    combine,
    fragile,
    group_by_file,
    minimize,
    redundant,
    unique,
)
from r2.core.coverage.base import CoverageMap, Outcome, Span, SpanKind, TestRecord


def line(path: str, n: int) -> Span:
    return Span.line(path, n)


def lines(path: str, *ns: int) -> frozenset[Span]:
    return frozenset(line(path, n) for n in ns)


def make_map(
    tests: dict[str, frozenset[Span]],
    *,
    runner: str = "pytest",
    kind: SpanKind = "line",
    ambient: frozenset[Span] = frozenset(),
    outcomes: dict[str, Outcome] | None = None,
) -> CoverageMap:
    outcomes = outcomes or {}
    return CoverageMap(
        runner=runner,
        span_kind=kind,
        tests={
            id: TestRecord(outcomes.get(id, "passed"), spans)
            for id, spans in tests.items()
        },
        ambient=ambient,
    )


def ref(id: str, runner: str = "pytest") -> TestRef:
    return TestRef(runner, id)


@pytest.fixture
def suite() -> Suite:
    """
    A miniature of the roman catalog: lines 1-2 are imports (ambient), the
    property tests cover the happy path (10-14), each rejection test adds
    its own error line, and two rejections share line 20.
    """
    return combine(
        [
            make_map(
                {
                    "prop::roundtrip": lines("r.py", 10, 11, 12, 13),
                    "prop::symbols": lines("r.py", 10, 11, 14),
                    "ex::returns_str": lines("r.py", 1, 10, 11),
                    "ex::roundtrip_small": lines("r.py", 10, 11, 12),
                    "ex::rejects_zero": lines("r.py", 10, 20),
                    "ex::rejects_4000": lines("r.py", 10, 20),
                    "ex::rejects_empty": lines("r.py", 12, 30, 31),
                },
                ambient=lines("r.py", 1, 2),
            )
        ]
    )


BASELINE = ["prop::*"]


# combine


def test_combine_keys_tests_by_runner() -> None:
    suite = combine(
        [
            make_map({"t > a": lines("a.ts", 1)}, runner="vitest", kind="block"),
            make_map({"t > a": lines("a.ts", 1)}, runner="playwright", kind="block"),
        ]
    )
    assert set(suite.tests) == {ref("t > a", "vitest"), ref("t > a", "playwright")}


def test_combine_unions_ambient() -> None:
    suite = combine(
        [
            make_map({}, ambient=lines("a.py", 1)),
            make_map({}, runner="vitest", ambient=lines("a.ts", 1)),
        ]
    )
    assert suite.ambient == lines("a.py", 1) | lines("a.ts", 1)


def test_combine_keeps_native_spans_when_kinds_agree() -> None:
    region = frozenset({Span.parse("a.rs:3:5-5:1")})
    suite = combine([make_map({"t": region}, runner="nextest", kind="region")])
    assert suite.tests[ref("t", "nextest")].spans == region


def test_combine_reduces_a_shared_file_to_lines_when_kinds_differ() -> None:
    block = frozenset({Span.parse("a.ts:3:0-4:9")})
    other = frozenset({Span.parse("b.ts:7:0-7:5")})
    suite = combine(
        [
            make_map({"v": block | other}, runner="vitest", kind="block"),
            make_map({"p": lines("a.ts", 3)}, runner="playwright", kind="line"),
        ]
    )
    assert suite.tests[ref("v", "vitest")].spans == lines("a.ts", 3, 4) | other


def test_combine_by_line_reduces_every_file() -> None:
    arc = frozenset({Span.parse("a.py:3:0-7:0")})
    suite = combine([make_map({"t": arc}, kind="arc")], by_line=True)
    assert suite.tests[ref("t")].spans == lines("a.py", 3, 7)


def test_combine_keeps_outcomes() -> None:
    suite = combine([make_map({"t": lines("a.py", 1)}, outcomes={"t": "failed"})])
    assert suite.tests[ref("t")].outcome == "failed"


# added


def test_added_ignores_ambient_and_baseline(suite: Suite) -> None:
    assert added(suite, ref("ex::rejects_empty"), BASELINE) == lines("r.py", 30, 31)


def test_baseline_test_adds_nothing(suite: Suite) -> None:
    assert added(suite, ref("prop::roundtrip"), BASELINE) == frozenset()


def test_added_without_baseline_is_everything_but_ambient(suite: Suite) -> None:
    assert added(suite, ref("ex::returns_str"), []) == lines("r.py", 10, 11)


# redundant


def test_redundant(suite: Suite) -> None:
    assert redundant(suite, BASELINE) == [
        ref("ex::returns_str"),
        ref("ex::roundtrip_small"),
    ]


def test_redundant_checks_only_selected_tests(suite: Suite) -> None:
    assert redundant(suite, BASELINE, ["*small"]) == [ref("ex::roundtrip_small")]


def test_tests_that_overlap_each_other_are_not_redundant(suite: Suite) -> None:
    # rejects_zero and rejects_4000 cover the same line, but the baseline
    # does not, so each one adds it.
    assert ref("ex::rejects_zero") not in redundant(suite, BASELINE)


def test_redundant_includes_failed_tests() -> None:
    suite = combine(
        [
            make_map(
                {"base": lines("a.py", 1), "t": lines("a.py", 1)},
                outcomes={"t": "failed"},
            )
        ]
    )
    assert redundant(suite, ["base"]) == [ref("t")]


# adds


def test_adds_sorted_by_count_then_test(suite: Suite) -> None:
    assert adds(suite, BASELINE) == [
        (ref("ex::rejects_empty"), lines("r.py", 30, 31)),
        (ref("ex::rejects_4000"), lines("r.py", 20)),
        (ref("ex::rejects_zero"), lines("r.py", 20)),
    ]


def test_adds_checks_only_selected_tests(suite: Suite) -> None:
    assert adds(suite, BASELINE, ["*zero"]) == [
        (ref("ex::rejects_zero"), lines("r.py", 20))
    ]


# unique


def test_unique(suite: Suite) -> None:
    assert unique(suite) == [
        (ref("ex::rejects_empty"), lines("r.py", 30, 31)),
        (ref("prop::roundtrip"), lines("r.py", 13)),
        (ref("prop::symbols"), lines("r.py", 14)),
    ]


def test_unique_with_selectors_still_compares_with_every_test(suite: Suite) -> None:
    assert unique(suite, ["ex::*"]) == [
        (ref("ex::rejects_empty"), lines("r.py", 30, 31))
    ]


def test_unique_ignores_ambient() -> None:
    suite = combine([make_map({"t": lines("a.py", 1, 2)}, ambient=lines("a.py", 1))])
    assert unique(suite) == [(ref("t"), lines("a.py", 2))]


# fragile


def test_fragile(suite: Suite) -> None:
    assert fragile(suite) == [
        (line("r.py", 13), ref("prop::roundtrip")),
        (line("r.py", 14), ref("prop::symbols")),
        (line("r.py", 30), ref("ex::rejects_empty")),
        (line("r.py", 31), ref("ex::rejects_empty")),
    ]


def test_fragile_filters_by_path() -> None:
    suite = combine([make_map({"t": lines("a.py", 1) | lines("b.py", 1)})])
    assert fragile(suite, ["b.py"]) == [(line("b.py", 1), ref("t"))]


# minimize


def test_minimize_keeps_baseline_then_greedy(suite: Suite) -> None:
    assert minimize(suite, BASELINE) == Minimized(
        kept=[
            ref("prop::roundtrip"),
            ref("prop::symbols"),
            ref("ex::rejects_empty"),
            ref("ex::rejects_4000"),
        ],
        dropped=[
            ref("ex::rejects_zero"),
            ref("ex::returns_str"),
            ref("ex::roundtrip_small"),
        ],
    )


def test_minimize_tie_goes_to_the_test_with_fewer_spans() -> None:
    # Once "base" is kept, "big" and "small" each add one span.
    tests = {
        "base": lines("f.py", 9),
        "big": lines("f.py", 1, 9),
        "small": lines("f.py", 2),
    }
    result = minimize(combine([make_map(tests)]), ["base"])
    assert result.kept == [ref("base"), ref("small"), ref("big")]


def test_minimize_full_tie_goes_to_the_smaller_ref() -> None:
    tests = {"b": lines("f.py", 1), "a": lines("f.py", 1)}
    assert minimize(combine([make_map(tests)])) == Minimized(
        kept=[ref("a")], dropped=[ref("b")]
    )


def test_minimize_without_baseline_covers_everything(suite: Suite) -> None:
    result = minimize(suite)
    covered = frozenset().union(*(suite.tests[t].spans for t in result.kept))
    every = frozenset().union(*(r.spans for r in suite.tests.values()))
    assert covered - suite.ambient == every - suite.ambient


def test_minimize_with_selectors_considers_only_them_and_the_baseline(
    suite: Suite,
) -> None:
    result = minimize(suite, BASELINE, ["*rejects_zero", "*returns_str"])
    assert result.kept == [
        ref("prop::roundtrip"),
        ref("prop::symbols"),
        ref("ex::rejects_zero"),
    ]
    assert result.dropped == [ref("ex::returns_str")]


# group_by_file


def test_group_by_file_merges_consecutive_lines() -> None:
    spans = lines("b.py", 1, 2, 3, 7) | lines("a.py", 5)
    assert group_by_file(spans, "line") == {"a.py": [(5, 5)], "b.py": [(1, 3), (7, 7)]}


def test_group_by_file_reduces_arcs_to_their_ends() -> None:
    spans = frozenset({Span.parse("a.py:3:0-9:0")})
    assert group_by_file(spans, "arc") == {"a.py": [(3, 3), (9, 9)]}
