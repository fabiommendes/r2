"""
Analyses over coverage maps. Pure functions: no I/O, no programs.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from r2.core.coverage.base import (
    CoverageMap,
    Span,
    SpanKind,
    TestId,
    TestRecord,
    matches,
)


@dataclass(frozen=True, order=True)
class TestRef:
    __test__ = False  # not a pytest test class

    runner: str
    id: TestId

    def __str__(self) -> str:
        return self.id


@dataclass(frozen=True)
class Suite:
    """
    The tests of several maps, with spans comparable across them.
    """

    tests: Mapping[TestRef, TestRecord]
    ambient: frozenset[Span]


@dataclass(frozen=True)
class Minimized:
    kept: list[TestRef]
    """Baseline tests first (sorted), then in the order they were picked."""
    dropped: list[TestRef]
    """Sorted."""


def combine(maps: Sequence[CoverageMap], *, by_line: bool = False) -> Suite:
    """
    Merge maps into one suite.

    A file measured by two maps with different span kinds has its spans
    reduced to lines in every map (`Span.to_lines`). A map measures the
    files in its `files` and the files of all its spans. `by_line` reduces every
    file. Ambient spans are the union of the maps' ambient spans, reduced
    the same way.
    """
    kinds: dict[str, set[SpanKind]] = {}
    for cmap in maps:
        for path in _measured(cmap):
            kinds.setdefault(path, set()).add(cmap.span_kind)
    mixed = {path for path, found in kinds.items() if len(found) > 1}

    def convert(cmap: CoverageMap, spans: frozenset[Span]) -> frozenset[Span]:
        result: set[Span] = set()
        for span in spans:
            if by_line or span.path in mixed:
                result |= span.to_lines(cmap.span_kind)
            else:
                result.add(span)
        return frozenset(result)

    tests: dict[TestRef, TestRecord] = {}
    ambient: set[Span] = set()
    for cmap in maps:
        ambient |= convert(cmap, cmap.ambient)
        for test_id, record in cmap.tests.items():
            ref = TestRef(cmap.runner, test_id)
            tests[ref] = TestRecord(record.outcome, convert(cmap, record.spans))
    return Suite(tests, frozenset(ambient))


def _measured(cmap: CoverageMap) -> set[str]:
    """
    Files a map measures: its `files` and the files of all its spans.
    """
    paths = set(cmap.files)
    paths.update(span.path for span in cmap.ambient)
    for record in cmap.tests.values():
        paths.update(span.path for span in record.spans)
    return paths


def _baseline_refs(suite: Suite, baseline: Sequence[str]) -> set[TestRef]:
    """
    Tests of the suite picked by the baseline selectors.
    """
    return {ref for ref in suite.tests if matches(baseline, ref.runner, ref.id)}


def _picked(suite: Suite, selectors: Sequence[str]) -> list[TestRef]:
    """
    Sorted tests picked by `selectors`, or every test without selectors.
    """
    return sorted(
        ref
        for ref in suite.tests
        if not selectors or matches(selectors, ref.runner, ref.id)
    )


def _covered(suite: Suite, refs: set[TestRef]) -> set[Span]:
    """
    Union of the spans of `refs`.
    """
    covered: set[Span] = set()
    for ref in refs:
        covered |= suite.tests[ref].spans
    return covered


def added(suite: Suite, test: TestRef, baseline: Sequence[str]) -> frozenset[Span]:
    """
    Spans `test` covers that neither the baseline tests nor the ambient
    spans cover. A baseline test adds nothing.
    """
    refs = _baseline_refs(suite, baseline)
    if test in refs:
        return frozenset()
    return suite.tests[test].spans - _covered(suite, refs) - suite.ambient


def redundant(
    suite: Suite, baseline: Sequence[str], selectors: Sequence[str] = ()
) -> list[TestRef]:
    """
    Tests outside the baseline that add no span, sorted. With selectors,
    only the tests they pick are checked.
    """
    outside = _baseline_refs(suite, baseline)
    return [
        ref
        for ref in _picked(suite, selectors)
        if ref not in outside and not added(suite, ref, baseline)
    ]


def adds(
    suite: Suite, baseline: Sequence[str], selectors: Sequence[str] = ()
) -> list[tuple[TestRef, frozenset[Span]]]:
    """
    Tests outside the baseline that add spans, with the spans they add.
    Sorted by the number of spans, largest first, then by test.
    """
    inside = _baseline_refs(suite, baseline)
    result = [
        (ref, extra)
        for ref in _picked(suite, selectors)
        if ref not in inside and (extra := added(suite, ref, baseline))
    ]
    return sorted(result, key=lambda item: (-len(item[1]), item[0]))


def unique(
    suite: Suite, selectors: Sequence[str] = ()
) -> list[tuple[TestRef, frozenset[Span]]]:
    """
    For each test, the spans no other test covers and that are not ambient.
    Tests with none are left out. Sorted by test. With selectors, only
    those tests are reported, but every test counts as "other".
    """
    counts = _span_counts(suite)
    result = []
    for ref in _picked(suite, selectors):
        own = frozenset(
            span
            for span in suite.tests[ref].spans
            if counts[span] == 1 and span not in suite.ambient
        )
        if own:
            result.append((ref, own))
    return result


def _span_counts(suite: Suite) -> Counter[Span]:
    """
    How many tests cover each span.
    """
    counts: Counter[Span] = Counter()
    for record in suite.tests.values():
        counts.update(record.spans)
    return counts


def fragile(suite: Suite, paths: Sequence[str] = ()) -> list[tuple[Span, TestRef]]:
    """
    Non-ambient spans covered by exactly one test, sorted by span. With
    paths, only spans whose file is one of them.
    """
    owners: dict[Span, TestRef] = {}
    counts = _span_counts(suite)
    for ref, record in suite.tests.items():
        for span in record.spans:
            if (
                counts[span] == 1
                and span not in suite.ambient
                and (not paths or span.path in paths)
            ):
                owners[span] = ref
    return sorted(owners.items())


def minimize(
    suite: Suite, baseline: Sequence[str] = (), selectors: Sequence[str] = ()
) -> Minimized:
    """
    Greedy set cover of the non-ambient spans the considered tests cover.

    Considered tests: the ones picked by `selectors` plus the baseline, or
    every test without selectors. The baseline is kept first. Then, while
    some test adds spans, keep the one that adds the most; ties go to the
    test with fewer spans in total, then to the smaller TestRef. Considered
    tests not kept are dropped.
    """
    base = _baseline_refs(suite, baseline)
    considered = set(_picked(suite, selectors)) | base
    spans = {ref: suite.tests[ref].spans - suite.ambient for ref in considered}
    kept = sorted(base)
    covered = set().union(*(spans[ref] for ref in kept)) if kept else set()
    pending = considered - base
    while pending:
        best = min(
            pending,
            key=lambda ref: (-len(spans[ref] - covered), len(spans[ref]), ref),
        )
        if not spans[best] - covered:
            break
        kept.append(best)
        covered |= spans[best]
        pending.discard(best)
    return Minimized(kept, sorted(considered - set(kept)))


def group_by_file(
    spans: frozenset[Span], kind: SpanKind
) -> Mapping[str, list[tuple[int, int]]]:
    """
    Spans as inclusive line ranges per file, after `Span.to_lines(kind)`.
    Files and ranges sorted; consecutive lines merged into one range.
    """
    lines: dict[str, set[int]] = {}
    for span in spans:
        for line in span.to_lines(kind):
            lines.setdefault(line.path, set()).add(line.start_line)
    result: dict[str, list[tuple[int, int]]] = {}
    for path in sorted(lines):
        ranges: list[tuple[int, int]] = []
        for number in sorted(lines[path]):
            if ranges and ranges[-1][1] == number - 1:
                ranges[-1] = (ranges[-1][0], number)
            else:
                ranges.append((number, number))
        result[path] = ranges
    return result
