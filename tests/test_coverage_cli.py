"""
Tests for the `r2 coverage` command group (dev/spec/coverage.md).

The analysis commands run in-process with Typer's CliRunner on maps written
by hand into `tmp_path`. One acceptance test runs `collect` for real on a
copy of tests/examples/roman/python.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import ClassVar

import pytest
from typer.testing import CliRunner, Result

from r2.cli.app import app
from r2.core.coverage.base import (
    CollectError,
    CoverageMap,
    CoverageRunner,
    MissingTool,
    Outcome,
    Progress,
    Span,
    SpanKind,
    TestRecord,
)
from r2.core.coverage.workspace import (
    collect,
    collect_lock,
    detect_runners,
    find_project_root,
    load_maps,
)
from r2.core.project.base import Project
from r2.core.project.py import UvProject
from tests.support import ExampleProjectFactory

cli = CliRunner()


def lines(path: str, *ns: int) -> frozenset[Span]:
    return frozenset(Span.line(path, n) for n in ns)


def make_map(
    tests: dict[str, frozenset[Span]],
    *,
    runner: str = "pytest",
    ambient: frozenset[Span] = frozenset(),
    outcomes: dict[str, Outcome] | None = None,
) -> CoverageMap:
    outcomes = outcomes or {}
    return CoverageMap(
        runner=runner,
        span_kind="line",
        tests={
            id: TestRecord(outcomes.get(id, "passed"), spans)
            for id, spans in tests.items()
        },
        ambient=ambient,
    )


ROMAN_MAP = make_map(
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
    outcomes={"ex::roundtrip_small": "failed"},
)


@pytest.fixture(autouse=True)
def _human_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("R2_AGENT", raising=False)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project folder holding ROMAN_MAP, as the current directory."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    ROMAN_MAP.save(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def r2(*args: str) -> Result:
    return cli.invoke(app, list(args))


def out_lines(result: Result) -> list[str]:
    return result.stdout.splitlines()


# workspace


def test_find_project_root_walks_up(tmp_path: Path) -> None:
    (tmp_path / "Cargo.toml").write_text("")
    (tmp_path / "src" / "deep").mkdir(parents=True)
    assert find_project_root(tmp_path / "src" / "deep") == tmp_path


def test_find_project_root_without_project(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        find_project_root(tmp_path)


def test_load_maps_sorted_by_runner(tmp_path: Path) -> None:
    make_map({}, runner="vitest").save(tmp_path)
    make_map({}, runner="pytest").save(tmp_path)
    assert [m.runner for m in load_maps(tmp_path)] == ["pytest", "vitest"]
    assert [m.runner for m in load_maps(tmp_path, ["vitest"])] == ["vitest"]


@pytest.mark.parametrize("names", [[], ["pytest"]])
def test_load_maps_missing(tmp_path: Path, names: list[str]) -> None:
    with pytest.raises(FileNotFoundError):
        load_maps(tmp_path, names)


def test_detect_runners(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[dependency-groups]\ndev = ["pytest"]\n'
    )
    assert [r.name for r in detect_runners(tmp_path)] == ["pytest"]


def test_detect_runner_by_name_that_is_not_there(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    with pytest.raises(ValueError):
        detect_runners(tmp_path, ["pytest"])


class FakeRunner(CoverageRunner):
    """Stands in for pytest: returns a fixed map instead of running tests."""

    name: ClassVar[str] = "pytest"
    span_kind: ClassVar[SpanKind] = "line"

    def __init__(self, root: Path, result: CoverageMap) -> None:
        (root / "pyproject.toml").write_text('[project]\nname = "x"\n')
        super().__init__(UvProject(root))
        self.result = result
        self.selectors: Sequence[str] = ()

    @classmethod
    def detect(cls, project: Project) -> bool:
        return True

    def missing_tools(self) -> list[MissingTool]:
        return []

    def suggestions(self) -> list[str]:
        return ["add speedup: run this"]

    def collect(
        self, selectors: Sequence[str] = (), progress: Progress | None = None
    ) -> CoverageMap:
        self.selectors = selectors
        if progress is not None:
            progress.started(len(self.result.tests))
            for id, record in self.result.tests.items():
                progress.finished(id, record.outcome)
            progress.reading()
        return self.result


def test_collect_saves_the_map(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ROMAN_MAP)
    assert collect(runner) == ROMAN_MAP
    assert CoverageMap.load(tmp_path, "pytest") == ROMAN_MAP


def test_collect_fails_while_another_collect_runs(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ROMAN_MAP)
    with collect_lock(tmp_path, "pytest"), pytest.raises(CollectError, match="running"):
        collect(runner)
    assert collect(runner) == ROMAN_MAP, "the lock is released on exit"


def test_collect_with_selectors_merges_into_the_saved_map(tmp_path: Path) -> None:
    ROMAN_MAP.save(tmp_path)
    fresh = make_map({"ex::rejects_zero": lines("r.py", 99)})
    runner = FakeRunner(tmp_path, fresh)
    merged = collect(runner, ["*zero"])
    assert runner.selectors == ["*zero"]
    assert merged.tests["ex::rejects_zero"].spans == lines("r.py", 99)
    assert merged.tests["prop::roundtrip"] == ROMAN_MAP.tests["prop::roundtrip"]
    assert CoverageMap.load(tmp_path, "pytest") == merged


# analysis commands


def test_redundant(project: Path) -> None:
    result = r2("coverage", "redundant", "--baseline", "prop::*")
    assert result.exit_code == 0, result.output
    assert out_lines(result) == ["ex::returns_str", "ex::roundtrip_small (failed)"]


def test_redundant_json(project: Path) -> None:
    result = r2("--json", "coverage", "redundant", "--baseline", "prop::*")
    assert json.loads(result.stdout) == [
        {
            "test": "ex::returns_str",
            "runner": "pytest",
            "outcome": "passed",
            "spans": 3,
        },
        {
            "test": "ex::roundtrip_small",
            "runner": "pytest",
            "outcome": "failed",
            "spans": 3,
        },
    ]


def test_redundant_needs_a_baseline(project: Path) -> None:
    assert r2("coverage", "redundant").exit_code == 2


def test_adds(project: Path) -> None:
    result = r2("coverage", "adds", "--baseline", "prop::*")
    assert out_lines(result) == [
        "ex::rejects_empty: 2 spans",
        "ex::rejects_4000: 1 span",
        "ex::rejects_zero: 1 span",
    ]


def test_adds_verbose_lists_line_ranges(project: Path) -> None:
    result = r2("-v", "coverage", "adds", "--baseline", "prop::*", "*empty")
    assert out_lines(result) == ["ex::rejects_empty: 2 spans", "  r.py: 30-31"]


def test_unique(project: Path) -> None:
    result = r2("coverage", "unique")
    assert out_lines(result) == [
        "ex::rejects_empty: 2 spans",
        "prop::roundtrip: 1 span",
        "prop::symbols: 1 span",
    ]


def test_fragile(project: Path) -> None:
    result = r2("coverage", "fragile")
    assert out_lines(result) == [
        "r.py:13  prop::roundtrip",
        "r.py:14  prop::symbols",
        "r.py:30-31  ex::rejects_empty",
    ]


def test_minimize(project: Path) -> None:
    result = r2("coverage", "minimize", "--baseline", "prop::*")
    assert out_lines(result) == [
        "prop::roundtrip",
        "prop::symbols",
        "ex::rejects_empty",
        "ex::rejects_4000",
        "kept 4 of 7 tests",
    ]


def test_minimize_json(project: Path) -> None:
    result = r2("--json", "coverage", "minimize", "--baseline", "prop::*")
    assert json.loads(result.stdout) == {
        "kept": [
            "prop::roundtrip",
            "prop::symbols",
            "ex::rejects_empty",
            "ex::rejects_4000",
        ],
        "dropped": ["ex::rejects_zero", "ex::returns_str", "ex::roundtrip_small"],
    }


def test_show(project: Path) -> None:
    result = r2("coverage", "show", "ex::rejects_empty", "--baseline", "prop::*")
    assert out_lines(result) == ["covers r.py: 12, 30-31", "adds r.py: 30-31"]


def test_show_without_baseline(project: Path) -> None:
    assert out_lines(r2("coverage", "show", "ex::rejects_empty")) == [
        "covers r.py: 12, 30-31"
    ]


def test_show_unknown_test(project: Path) -> None:
    result = r2("coverage", "show", "ex::nope")
    assert result.exit_code == 1
    assert "ex::nope" in result.stderr


def test_missing_map_points_to_collect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    monkeypatch.chdir(tmp_path)
    result = r2("coverage", "unique")
    assert result.exit_code == 1
    assert "r2 coverage collect" in result.stderr


def test_stale_map_warns_and_still_runs(project: Path) -> None:
    (project / "r.py").write_text("changed\n")
    stale = make_map({"t": lines("r.py", 1)})
    stale = replace(stale, files={"r.py": "0" * 64})
    stale.save(project)
    result = r2("coverage", "unique")
    assert result.exit_code == 0
    assert out_lines(result) == ["t: 1 span"]
    assert "warning" in result.stderr and "r.py" in result.stderr


def test_runner_filter(project: Path) -> None:
    make_map({"v > only": lines("a.ts", 1)}, runner="vitest").save(project)
    result = r2("coverage", "unique", "--runner", "vitest")
    assert out_lines(result) == ["v > only: 1 span"]


# collect


def test_collect_without_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    monkeypatch.chdir(tmp_path)
    result = r2("coverage", "collect")
    assert result.exit_code == 1
    assert "error" in result.stderr


def test_collect_reports_missing_tools(
    roman_project: ExampleProjectFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(roman_project("python"))
    monkeypatch.setenv("PATH", str(tmp_path))
    result = r2("coverage", "collect")
    assert result.exit_code == 1
    assert "uv" in result.stderr


@pytest.fixture
def fake_collect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = make_map(
        {"t::ok": lines("a.py", 1), "t::bad": lines("a.py", 2)},
        outcomes={"t::bad": "failed"},
    )
    runner = FakeRunner(tmp_path, result)
    monkeypatch.setattr(
        "r2.cli.coverage.detect_runners", lambda root, names=(): [runner]
    )
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("fake_collect")
def test_collect_shows_progress() -> None:
    result = r2("coverage", "collect")
    assert result.exit_code == 0, result.output
    assert out_lines(result) == ["pytest: 2 tests, 1 failed"]
    assert "pytest: running 2 tests" in result.stderr
    assert "FAILED t::bad" in result.stderr
    assert "add speedup: run this" in result.stderr
    assert "t::ok" not in result.stderr


@pytest.mark.usefixtures("fake_collect")
@pytest.mark.parametrize("flag", ["--agent", "--json"])
def test_collect_hides_progress_in_agent_and_json_mode(flag: str) -> None:
    result = r2(flag, "coverage", "collect")
    assert result.exit_code == 0, result.output
    assert out_lines(result) == ["pytest: 2 tests, 1 failed"]
    assert result.stderr == ""


def test_collect_error_shows_runner_output(
    roman_project: ExampleProjectFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(
        self: object, selectors: Sequence[str] = (), progress: object = None
    ) -> CoverageMap:
        raise CollectError(
            "pytest could not collect", "line 1\nE   SyntaxError: boom\n"
        )

    monkeypatch.setattr("r2.core.coverage.py.PytestCoverage.collect", fail)
    monkeypatch.chdir(roman_project("python"))
    result = r2("coverage", "collect")
    assert result.exit_code == 1
    assert "SyntaxError: boom" in result.stderr


def test_acceptance_on_roman_python(
    roman_project: ExampleProjectFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = roman_project("python")
    monkeypatch.chdir(root / "tests")  # any folder inside the project

    result = r2("coverage", "collect")
    assert result.exit_code == 0, result.output
    assert out_lines(result) == ["pytest: 12 tests, 0 failed"]
    assert (root / ".r2" / "coverage" / "pytest.json").is_file()

    baseline = ("--baseline", "tests/test_properties.py::*")
    assert out_lines(r2("coverage", "redundant", *baseline)) == [
        "tests/test_examples.py::test_from_roman_iv",
        "tests/test_examples.py::test_roundtrip_small",
        "tests/test_examples.py::test_to_roman_known_values",
        "tests/test_examples.py::test_to_roman_returns_str",
    ]

    kept = out_lines(r2("coverage", "minimize", *baseline))
    assert kept[-1] == "kept 7 of 12 tests"
    rejects = {
        "tests/test_examples.py::test_to_roman_rejects_zero",
        "tests/test_examples.py::test_to_roman_rejects_4000",
    }
    assert len(rejects & set(kept)) == 1
