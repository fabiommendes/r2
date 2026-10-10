"""
Per-test coverage for pytest, through coverage.py dynamic contexts.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, cast

from r2.core.cli_tool import CliTool
from r2.core.coverage.base import (
    COVERAGE_DIR,
    CollectError,
    CoverageMap,
    CoverageRunner,
    MissingTool,
    Outcome,
    Progress,
    Span,
    SpanKind,
    TestRecord,
    matches,
)
from r2.core.mode import VERBOSE, mode
from r2.core.project.base import Project
from r2.core.project.py import UvProject, uv

_PHASES = ("setup", "run", "teardown")
_SCHEMA = 7
"""The coverage.py data file schema r2 reads."""
_MARKER = "##r2 "
"""Prefix of the progress lines r2's pytest plugin prints."""

_OUTCOMES_PLUGIN = '''
"""
Pytest plugin written by r2: records the outcome of each test and prints
progress markers r2 reads while pytest runs. Under pytest-xdist it only
acts in the controller, which receives every worker's reports.
"""

import json
import os

import pytest

outcomes = {}
config = None


def marker(text):
    # Looked up late: pytest registers its reporter after this plugin loads.
    reporter = config and config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line("##r2 " + text)
        reporter.flush()


def pytest_configure(config):
    if not hasattr(config, "workerinput"):
        globals()["config"] = config


def pytest_collection_finish(session):
    if config is not None and not config.pluginmanager.has_plugin("dsession"):
        marker(f"started {len(session.items)}")


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_node_collection_finished(node, ids):
    global started
    if not started:
        started = True
        marker(f"started {len(ids)}")


started = False


def pytest_runtest_logreport(report):
    if config is None:
        return
    if report.failed:
        new = "failed"
    elif report.skipped:
        new = "skipped"
    elif report.when == "call":
        new = "passed"
    else:
        return
    if outcomes.get(report.nodeid) != "failed":
        outcomes[report.nodeid] = new


def pytest_runtest_logfinish(nodeid, location):
    if nodeid in outcomes:
        marker(f"finished {outcomes[nodeid]} {nodeid}")


def pytest_sessionfinish(session):
    if config is None:
        return
    with open(os.environ["R2_PYTEST_OUTCOMES"], "w") as file:
        json.dump(outcomes, file)
'''


class PytestCoverage(CoverageRunner):
    """
    Runs pytest once with `--cov-context=test` and branch coverage, then
    reads the coverage data: arcs recorded under a test's context belong to
    that test (setup, call and teardown alike), arcs under the empty
    context are ambient.

    Uses the project's pytest-cov when it is a dependency, else adds it for
    the run with `uv run --with pytest-cov`. The data file and any report
    go under `.r2/coverage/`; the project's own coverage settings (source,
    omit) are honoured.
    """

    name: ClassVar[str] = "pytest"
    span_kind: ClassVar[SpanKind] = "arc"

    @classmethod
    def detect(cls, project: Project) -> bool:
        """
        A uv project with pytest among its dependencies.
        """
        return isinstance(project, UvProject) and "pytest" in project.any_dependencies

    def missing_tools(self) -> list[MissingTool]:
        """
        `uv` when it is not on PATH.
        """
        if uv.available():
            return []
        return [MissingTool(uv.name, uv.install_hint)]

    def suggestions(self) -> list[str]:
        """
        Adding pytest-xdist, when the project lacks it, so `collect` runs
        the tests in parallel.
        """
        if self._parallel_args():
            return []
        return [
            "add pytest-xdist to run the tests in parallel: uv add --dev pytest-xdist"
        ]

    def collect(
        self, selectors: Sequence[str] = (), progress: Progress | None = None
    ) -> CoverageMap:
        """
        See `CoverageRunner.collect`. Selectors are resolved against the ids
        pytest collects. Records the outcome of each test, the sha256 of
        every measured file and the git commit and dirty state of the
        project, when it is in a git repository.
        """
        root = self._root()
        folder = root / COVERAGE_DIR
        folder.mkdir(parents=True, exist_ok=True)
        data_file = folder / "pytest.coverage"
        outcomes_file = folder / "pytest.outcomes.json"
        data_file.unlink(missing_ok=True)
        outcomes_file.unlink(missing_ok=True)
        (folder / "r2_pytest_outcomes.py").write_text(_OUTCOMES_PLUGIN)

        with_args = self._with_args()
        ids = self._resolve(selectors, with_args)
        env = {
            "COVERAGE_FILE": str(data_file),
            "R2_PYTEST_OUTCOMES": str(outcomes_file),
            "PYTHONPATH": os.pathsep.join(
                filter(None, [str(folder), os.environ.get("PYTHONPATH", "")])
            ),
        }
        done = _uv().call(
            "run",
            *with_args,
            "pytest",
            "--cov",
            "--cov-context=test",
            "--cov-branch",
            "--cov-report=",
            "-p",
            "no:cacheprovider",
            "-p",
            "r2_pytest_outcomes",
            *self._parallel_args(),
            *ids,
            _path=root,
            _env=env,
            _on_line=lambda line: _report(line, progress),
        )
        output = _without_markers(done.stdout) + done.stderr
        if done.returncode not in (0, 1):
            raise CollectError(f"pytest exited with {done.returncode}", output)
        if not outcomes_file.exists() or not data_file.exists():
            raise CollectError("pytest produced no coverage data", output)
        outcomes: dict[str, Outcome] = json.loads(outcomes_file.read_text())
        if progress is not None:
            progress.reading()

        return self._build(read_coverage_data(data_file), outcomes)

    def _root(self) -> Path:
        """
        The project root. Only uv projects are detected, so it is always one.
        """
        assert isinstance(self.project, UvProject)
        return self.project.root

    def _with_args(self) -> list[str]:
        """
        `uv run` options adding pytest-cov when the project lacks it.
        """
        project = self.project
        if isinstance(project, UvProject) and "pytest-cov" in project.any_dependencies:
            return []
        return ["--with", "pytest-cov"]

    def _parallel_args(self) -> list[str]:
        """
        `-n auto` when the project has pytest-xdist.
        """
        project = self.project
        if (
            isinstance(project, UvProject)
            and "pytest-xdist" in project.any_dependencies
        ):
            return ["-n", "auto"]
        return []

    def _resolve(self, selectors: Sequence[str], with_args: list[str]) -> list[str]:
        """
        The node ids picked by `selectors` among the ones pytest collects.
        """
        if not selectors:
            return []
        done = _uv().call(
            "run",
            *with_args,
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            _path=self._root(),
        )
        output = done.stdout + done.stderr
        if done.returncode != 0:
            raise CollectError(f"pytest exited with {done.returncode}", output)
        collected = [line for line in done.stdout.splitlines() if "::" in line]
        ids = [i for i in collected if matches(selectors, self.name, i)]
        if not ids:
            raise CollectError("no test matches the selectors", output)
        return ids

    def _build(
        self, dump: dict[str, object], outcomes: dict[str, Outcome]
    ) -> CoverageMap:
        """
        The coverage map from the reader's dump and the recorded outcomes.
        """
        root = self._root()
        spans: dict[str, set[Span]] = {test_id: set() for test_id in outcomes}
        ambient: set[Span] = set()
        contexts = cast(dict[str, dict[str, list[list[int]]]], dump["contexts"])
        for context, per_file in contexts.items():
            test_id, _, phase = context.rpartition("|")
            found: set[Span] = set()
            for name, arcs in per_file.items():
                path = _relative(name, root)
                if path is not None:
                    found.update(Span(path, a, 0, b, 0) for a, b in arcs)
            if not context:
                ambient |= found
            elif phase in _PHASES and test_id in spans:
                spans[test_id] |= found
        files = {}
        for name in cast(list[str], dump["files"]):
            path = _relative(name, root)
            if path is not None and (root / path).is_file():
                files[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
        tests = {
            test_id: TestRecord(
                outcome, frozenset() if outcome == "skipped" else frozenset(found)
            )
            for test_id, outcome in outcomes.items()
            for found in [spans[test_id]]
        }
        commit, dirty = _git_state(root)
        return CoverageMap(
            runner=self.name,
            span_kind=self.span_kind,
            tests=tests,
            ambient=frozenset(ambient),
            files=files,
            created=datetime.now(UTC).isoformat(timespec="seconds"),
            commit=commit,
            dirty=dirty,
        )


def read_coverage_data(data_file: Path) -> dict[str, object]:
    """
    The measured files and the arcs of each context in a coverage.py data
    file, as `{"files": [path], "contexts": {context: {path: [[a, b]]}}}`.

    Reads the SQLite file directly: coverage.py's API filters contexts with
    a regex scan per query, which takes minutes on large suites. Raise
    CollectError for a schema other than 7, the one since coverage 5.0.
    """
    with closing(sqlite3.connect(data_file)) as db:
        try:
            (version,) = db.execute("select version from coverage_schema").fetchone()
            if version != _SCHEMA:
                raise CollectError(f"unsupported coverage data schema {version}", "")
            files = sorted(path for (path,) in db.execute("select path from file"))
            rows = db.execute(
                "select context.context, file.path, arc.fromno, arc.tono from arc"
                " join file on file.id = arc.file_id"
                " join context on context.id = arc.context_id"
            ).fetchall()
        except sqlite3.Error as exc:
            raise CollectError(f"could not read the coverage data: {exc}", "") from exc
    contexts: dict[str, dict[str, list[list[int]]]] = {}
    for context, path, start, end in rows:
        contexts.setdefault(context, {}).setdefault(path, []).append([start, end])
    return {"files": files, "contexts": contexts}


def _uv() -> CliTool:
    """
    The `uv` tool, echoing the commands it runs only at verbose level.
    """
    return replace(uv, echo=mode.verbosity >= VERBOSE)


def _report(line: str, progress: Progress | None) -> None:
    """
    Pass a progress marker line from the pytest plugin to `progress`.
    """
    # Under xdist a marker may follow progress dots on the same line.
    _, found, marker = line.partition(_MARKER)
    if progress is None or not found:
        return
    event, _, rest = marker.partition(" ")
    if event == "started":
        progress.started(int(rest))
    elif event == "finished":
        outcome, _, test_id = rest.partition(" ")
        progress.finished(test_id, cast(Outcome, outcome))


def _without_markers(output: str) -> str:
    """
    `output` without the plugin's progress markers.
    """
    kept = []
    for line in output.splitlines():
        before, found, _ = line.partition(_MARKER)
        if before or not found:
            kept.append(before + "\n")
    return "".join(kept)


def _relative(name: str, root: Path) -> str | None:
    """
    `name` as a posix path relative to `root`, or None when outside it or
    under `.r2/`, where r2's own pytest plugin lives.
    """
    try:
        path = Path(name).resolve().relative_to(root.resolve())
    except ValueError:
        return None
    if path.parts[:1] == (COVERAGE_DIR.parts[0],):
        return None
    return path.as_posix()


def _git_state(root: Path) -> tuple[str | None, bool]:
    """
    The HEAD commit and whether the tree has changes outside `.r2/`, or
    `(None, False)` when `root` is not in a git repository.
    """
    git = CliTool("git", echo=False)
    head = git.call("rev-parse", "HEAD", _path=root)
    if head.returncode != 0:
        return None, False
    status = git.call("status", "--porcelain", "--", ".", ":(exclude).r2", _path=root)
    return head.stdout.strip(), bool(status.stdout.strip())
