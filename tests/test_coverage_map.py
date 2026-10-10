"""
Tests for r2.core.coverage.base: spans, selectors and coverage maps.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from r2.core.coverage.base import CoverageMap, Span, SpanKind, TestRecord, matches


def span(text: str) -> Span:
    return Span.parse(text)


def make_map(**changes: Any) -> CoverageMap:
    base = CoverageMap(
        runner="pytest",
        span_kind="arc",
        tests={
            "tests/test_a.py::test_one": TestRecord(
                "passed", frozenset({span("src/a.py:1:0-2:0")})
            ),
            "tests/test_a.py::test_two": TestRecord(
                "failed", frozenset({span("src/a.py:2:0-3:0")})
            ),
        },
        ambient=frozenset({span("src/a.py:-1:0-1:0")}),
        files={"src/a.py": "0" * 64},
        created="2026-10-10T12:00:00+00:00",
        commit="abc123",
        dirty=True,
    )
    return replace(base, **changes)


# Spans


@pytest.mark.parametrize(
    "text",
    [
        "src/a.py:1:0-2:0",
        "src/a.py:-3:0-7:0",
        "src/lib.rs:10:5-12:40",
        "a b/c.ts:1:1-1:9",
    ],
)
def test_span_text_round_trips(text: str) -> None:
    assert str(Span.parse(text)) == text


def test_span_parse_reads_fields() -> None:
    assert Span.parse("src/lib.rs:10:5-12:40") == Span("src/lib.rs", 10, 5, 12, 40)


def test_span_path_may_hold_colons() -> None:
    assert Span.parse("C:/x/a.py:1:0-2:0").path == "C:/x/a.py"


@pytest.mark.parametrize("text", ["", "src/a.py", "src/a.py:1:0", "src/a.py:a:0-1:0"])
def test_malformed_span_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        Span.parse(text)


def test_line_span() -> None:
    assert Span.line("a.py", 4) == Span("a.py", 4, 0, 4, 0)


@pytest.mark.parametrize(
    ("text", "kind", "lines"),
    [
        ("a.py:3:0-7:0", "arc", {3, 7}),
        ("a.py:7:0-3:0", "arc", {3, 7}),
        ("a.py:-2:0-5:0", "arc", {2, 5}),
        ("a.py:4:0--4:0", "arc", {4}),
        ("a.py:0:0-5:0", "arc", {5}),
        ("a.rs:3:5-5:1", "region", {3, 4, 5}),
        ("a.ts:2:0-2:9", "block", {2}),
        ("a.py:6:0-6:0", "line", {6}),
    ],
)
def test_to_lines(text: str, kind: SpanKind, lines: set[int]) -> None:
    path = text.split(":")[0]
    expected = frozenset(Span.line(path, n) for n in lines)
    assert Span.parse(text).to_lines(kind) == expected


# Selectors


@pytest.mark.parametrize(
    ("selector", "runner", "test", "picked"),
    [
        ("*properties*", "pytest", "tests/test_properties.py::test_roundtrip", True),
        ("*properties*", "pytest", "tests/test_examples.py::test_iv", False),
        ("tests/test_x.py::test_a", "pytest", "tests/test_x.py::test_a", True),
        ("tests/test_x.py::test_a", "pytest", "tests/test_x.py::test_ab", False),
        ("test_a", "pytest", "tests/test_x.py::test_a", False),
        ("tests/t.py::test_p[1]", "pytest", "tests/t.py::test_p[1]", True),
        ("vitest:*properties*", "vitest", "tests/unit/properties.test.ts > rt", True),
        (
            "vitest:*properties*",
            "playwright",
            "tests/e2e/properties.spec.ts > rt",
            False,
        ),
        ("pytest:tests/x.py::*", "pytest", "tests/x.py::test_a", True),
    ],
)
def test_selector(selector: str, runner: str, test: str, picked: bool) -> None:
    assert matches([selector], runner, test) is picked


def test_selectors_combine_with_or() -> None:
    assert matches(["*one*", "*two*"], "pytest", "t::two")


def test_no_selectors_pick_nothing() -> None:
    assert not matches([], "pytest", "t::one")


# Maps


def test_map_json_round_trips() -> None:
    cov = make_map()
    assert CoverageMap.from_json(cov.to_json()) == cov


def test_map_json_is_deterministic() -> None:
    tests = dict(reversed(list(make_map().tests.items())))
    assert make_map(tests=tests).to_json() == make_map().to_json()


def test_map_json_layout() -> None:
    data = json.loads(make_map().to_json())
    assert data["version"] == 1
    assert data["runner"] == "pytest"
    assert data["span_kind"] == "arc"
    assert data["ambient"] == ["src/a.py:-1:0-1:0"]
    assert data["tests"]["tests/test_a.py::test_two"] == {
        "outcome": "failed",
        "spans": ["src/a.py:2:0-3:0"],
    }


def test_map_of_other_version_is_rejected() -> None:
    data = json.loads(make_map().to_json())
    data["version"] = 99
    with pytest.raises(ValueError):
        CoverageMap.from_json(json.dumps(data))


def test_save_and_load(tmp_path: Path) -> None:
    cov = make_map()
    path = cov.save(tmp_path)
    assert path == tmp_path / ".r2" / "coverage" / "pytest.json"
    assert CoverageMap.load(tmp_path, "pytest") == cov


def test_save_ignores_r2_folder_in_git(tmp_path: Path) -> None:
    make_map().save(tmp_path)
    assert (tmp_path / ".r2" / ".gitignore").read_text().strip() == "*"


def test_save_keeps_existing_gitignore(tmp_path: Path) -> None:
    (tmp_path / ".r2").mkdir()
    (tmp_path / ".r2" / ".gitignore").write_text("custom\n")
    make_map().save(tmp_path)
    assert (tmp_path / ".r2" / ".gitignore").read_text() == "custom\n"


def test_load_missing_map(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        CoverageMap.load(tmp_path, "pytest")


def test_stale_files(tmp_path: Path) -> None:
    for name in ["same.py", "changed.py"]:
        (tmp_path / name).write_text("x = 1\n")
    digest = hashlib.sha256(b"x = 1\n").hexdigest()
    files = {"same.py": digest, "changed.py": digest, "gone.py": digest}
    (tmp_path / "changed.py").write_text("x = 2\n")
    assert make_map(files=files).stale_files(tmp_path) == ["changed.py", "gone.py"]


def test_merge_replaces_selected_tests_only() -> None:
    old = make_map()
    fresh = TestRecord("passed", frozenset({span("src/a.py:9:0-9:0")}))
    newer = make_map(
        tests={"tests/test_a.py::test_two": fresh},
        ambient=frozenset(),
        created="2026-10-11T00:00:00+00:00",
    )
    merged = old.merge(newer, ["*test_two"])
    assert merged.tests == {
        "tests/test_a.py::test_one": old.tests["tests/test_a.py::test_one"],
        "tests/test_a.py::test_two": fresh,
    }
    assert merged.ambient == frozenset()
    assert merged.created == "2026-10-11T00:00:00+00:00"


def test_merge_drops_selected_tests_that_disappeared() -> None:
    merged = make_map().merge(make_map(tests={}), ["*test_two"])
    assert set(merged.tests) == {"tests/test_a.py::test_one"}


def test_merge_without_selectors_is_the_newer_map() -> None:
    newer = make_map(tests={})
    assert make_map().merge(newer, []) == newer
