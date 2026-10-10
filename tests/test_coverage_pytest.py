"""
Tests for r2.core.coverage.py.PytestCoverage, against copies of
tests/examples/roman/python. The collect tests run pytest for real, so they
bundle their assertions.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from r2.core.coverage.analysis import TestRef, combine, redundant
from r2.core.coverage.base import (
    CollectError,
    CoverageMap,
    MissingTool,
    Outcome,
    TestId,
)
from r2.core.coverage.py import PytestCoverage, read_coverage_data
from r2.core.project.py import UvProject
from tests.support import ExampleProjectFactory

EXAMPLES = "tests/test_examples.py::"
PROPERTIES = "tests/test_properties.py::"

CATALOG = [
    PROPERTIES + "test_roundtrip",
    PROPERTIES + "test_to_roman_uses_only_roman_symbols",
    EXAMPLES + "test_to_roman_known_values",
    EXAMPLES + "test_to_roman_returns_str",
    EXAMPLES + "test_from_roman_iv",
    EXAMPLES + "test_roundtrip_small",
    EXAMPLES + "test_to_roman_rejects_zero",
    EXAMPLES + "test_to_roman_rejects_4000",
    EXAMPLES + "test_from_roman_rejects_empty",
    EXAMPLES + "test_from_roman_rejects_invalid_symbol",
    EXAMPLES + "test_from_roman_rejects_out_of_range",
    EXAMPLES + "test_from_roman_rejects_non_canonical",
]

REDUNDANT = [
    EXAMPLES + "test_from_roman_iv",
    EXAMPLES + "test_roundtrip_small",
    EXAMPLES + "test_to_roman_known_values",
    EXAMPLES + "test_to_roman_returns_str",
]


@pytest.fixture
def roman(roman_project: ExampleProjectFactory) -> Path:
    return roman_project("python")


def sources(root: Path) -> dict[Path, bytes]:
    files = [
        root / "pyproject.toml",
        *root.glob("src/**/*.py"),
        *root.glob("tests/*.py"),
    ]
    return {p: p.read_bytes() for p in files}


class Recorder:
    """
    A Progress that records the events it receives.
    """

    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []

    def started(self, total: int) -> None:
        self.events.append(("started", total))

    def finished(self, test: TestId, outcome: Outcome) -> None:
        self.events.append(("finished", test, outcome))

    def reading(self) -> None:
        self.events.append(("reading",))


def runner_for(root: Path) -> PytestCoverage:
    return PytestCoverage(UvProject(root))


# detect / missing_tools


def test_detects_a_uv_project_with_pytest(roman: Path) -> None:
    assert PytestCoverage.detect(UvProject(roman))


def test_ignores_a_uv_project_without_pytest(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert not PytestCoverage.detect(UvProject(tmp_path))


def test_missing_uv(
    roman: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    missing = runner_for(roman).missing_tools()
    assert [tool.name for tool in missing] == ["uv"]
    assert all(isinstance(tool, MissingTool) and tool.install for tool in missing)


def test_suggests_xdist(roman: Path) -> None:
    assert runner_for(roman).suggestions() == [
        "add pytest-xdist to run the tests in parallel: uv add --dev pytest-xdist"
    ]


def test_no_suggestion_with_xdist(roman: Path) -> None:
    pyproject = roman / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            '"pytest-cov>=6"', '"pytest-cov>=6", "pytest-xdist"'
        )
    )
    assert runner_for(roman).suggestions() == []


def test_nothing_missing(roman: Path) -> None:
    assert runner_for(roman).missing_tools() == []


# collect


def test_collect_whole_suite(roman: Path) -> None:
    before = sources(roman)
    cov = runner_for(roman).collect()

    assert cov.runner == "pytest"
    assert cov.span_kind == "arc"
    assert sorted(cov.tests) == sorted(CATALOG)
    assert {record.outcome for record in cov.tests.values()} == {"passed"}
    assert cov.ambient, "module level code of roman runs at import"

    source = roman / "src" / "roman" / "__init__.py"
    assert cov.files == {
        "src/roman/__init__.py": hashlib.sha256(source.read_bytes()).hexdigest()
    }
    assert {span.path for r in cov.tests.values() for span in r.spans} == {
        "src/roman/__init__.py"
    }
    assert cov.stale_files(roman) == []
    assert cov.created

    suite = combine([cov])
    assert redundant(suite, [PROPERTIES + "*"]) == [
        TestRef("pytest", id) for id in REDUNDANT
    ]

    assert sources(roman) == before, "collect changed the project's files"


def test_collect_is_deterministic(roman: Path) -> None:
    runner = runner_for(roman)
    first, second = runner.collect(), runner.collect()
    assert first.tests == second.tests
    assert first.ambient == second.ambient


def test_collect_with_selectors_runs_only_those(roman: Path) -> None:
    cov = runner_for(roman).collect(["*rejects_zero", PROPERTIES + "*"])
    assert sorted(cov.tests) == sorted(
        [
            EXAMPLES + "test_to_roman_rejects_zero",
            PROPERTIES + "test_roundtrip",
            PROPERTIES + "test_to_roman_uses_only_roman_symbols",
        ]
    )


def test_failing_test_is_recorded(roman: Path) -> None:
    path = roman / "tests" / "test_examples.py"
    path.write_text(
        path.read_text()
        + "\n\ndef test_broken() -> None:\n    assert to_roman(1) == 'X'\n"
    )
    cov = runner_for(roman).collect()
    broken = cov.tests[EXAMPLES + "test_broken"]
    assert broken.outcome == "failed"
    assert broken.spans
    assert cov.tests[EXAMPLES + "test_from_roman_iv"].outcome == "passed"


def test_collect_reports_progress(roman: Path) -> None:
    path = roman / "tests" / "test_examples.py"
    path.write_text(
        path.read_text()
        + "\n\ndef test_broken() -> None:\n    assert to_roman(1) == 'X'\n"
    )
    progress = Recorder()
    runner_for(roman).collect(progress=progress)
    events = progress.events
    assert events[0] == ("started", 13)
    assert events[-1] == ("reading",)
    assert sorted(events[1:-1]) == sorted(
        [("finished", id, "passed") for id in CATALOG]
        + [("finished", EXAMPLES + "test_broken", "failed")]
    )


def test_collection_error_output_hides_progress_markers(roman: Path) -> None:
    (roman / "tests" / "test_syntax.py").write_text("def broken(:\n")
    with pytest.raises(CollectError) as info:
        runner_for(roman).collect(progress=Recorder())
    assert "test_syntax.py" in info.value.output
    assert "##r2" not in info.value.output


def test_skipped_test_has_no_spans(roman: Path) -> None:
    path = roman / "tests" / "test_examples.py"
    path.write_text(
        path.read_text()
        + "\n\n@pytest.mark.skip\ndef test_skipped() -> None:\n    to_roman(1)\n"
    )
    record = runner_for(roman).collect().tests[EXAMPLES + "test_skipped"]
    assert record.outcome == "skipped"
    assert record.spans == frozenset()


def test_collection_error_raises(roman: Path) -> None:
    (roman / "tests" / "test_syntax.py").write_text("def broken(:\n")
    with pytest.raises(CollectError) as info:
        runner_for(roman).collect()
    assert "test_syntax.py" in info.value.output


def test_map_round_trips_through_disk(roman: Path) -> None:
    cov = runner_for(roman).collect([PROPERTIES + "test_roundtrip"])
    cov.save(roman)
    assert CoverageMap.load(roman, "pytest") == cov


def test_unknown_coverage_schema_raises(tmp_path: Path) -> None:
    data_file = tmp_path / "data.coverage"
    with closing(sqlite3.connect(data_file)) as db, db:
        db.execute("create table coverage_schema (version integer)")
        db.execute("insert into coverage_schema values (99)")
    with pytest.raises(CollectError, match="schema 99"):
        read_coverage_data(data_file)


def test_collect_runs_in_parallel_with_xdist(roman: Path) -> None:
    serial = runner_for(roman).collect()
    pyproject = roman / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            '"pytest-cov>=6"', '"pytest-cov>=6", "pytest-xdist"'
        )
    )
    (roman / "tests" / "test_worker.py").write_text(
        "import os, pathlib\n\n\ndef test_worker() -> None:\n"
        "    worker = os.environ.get('PYTEST_XDIST_WORKER', '')\n"
        "    pathlib.Path('worker.txt').write_text(worker)\n"
    )
    progress = Recorder()
    parallel = runner_for(roman).collect(progress=progress)
    assert (roman / "worker.txt").read_text().startswith("gw")
    worker = "tests/test_worker.py::test_worker"
    assert {k: v for k, v in parallel.tests.items() if k != worker} == serial.tests
    assert progress.events[0] == ("started", 13)
    assert len(progress.events) == 15


def test_r2_scratch_files_are_not_measured(roman: Path) -> None:
    pyproject = roman / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace('source = ["roman"]\n', ""))
    cov = runner_for(roman).collect([PROPERTIES + "test_roundtrip"])
    paths = {sp.path for r in cov.tests.values() for sp in r.spans}
    paths |= {sp.path for sp in cov.ambient} | set(cov.files)
    assert "tests/test_properties.py" in paths, "measures the whole folder"
    assert not [p for p in paths if p.startswith(".r2/")]
