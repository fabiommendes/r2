"""
Per-test coverage for pytest, through coverage.py dynamic contexts.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
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
_MARKER = "##r2 "
"""Prefix of the progress lines r2's pytest plugin prints."""

_OUTCOMES_PLUGIN = '''
"""
Pytest plugin written by r2: records the outcome of each test and prints
progress markers r2 reads while pytest runs.
"""

import json
import os

outcomes = {}
config = None


def marker(text):
    # Looked up late: pytest registers its reporter after this plugin loads.
    reporter = config and config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line("##r2 " + text)
        reporter.flush()


def pytest_configure(config):
    globals()["config"] = config


def pytest_collection_finish(session):
    marker(f"started {len(session.items)}")


def pytest_runtest_logfinish(nodeid, location):
    if nodeid in outcomes:
        marker(f"finished {outcomes[nodeid]} {nodeid}")


def pytest_runtest_logreport(report):
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


def pytest_sessionfinish(session):
    with open(os.environ["R2_PYTEST_OUTCOMES"], "w") as file:
        json.dump(outcomes, file)
'''

_READER = '''
"""
Script written by r2: dumps the arcs of a coverage data file per context.
"""

import json
import os
import re
import sys

from coverage import CoverageData

data_file, root = sys.argv[1:3]
data = CoverageData(basename=data_file)
data.read()
files = sorted(data.measured_files())
contexts = {}
for context in sorted(data.measured_contexts()):
    data.set_query_contexts(["^" + re.escape(context) + "$"])
    arcs = {}
    for name in files:
        found = data.arcs(name)
        if found:
            arcs[name] = sorted(found)
    contexts[context] = arcs
json.dump({"files": files, "contexts": contexts}, sys.stdout)
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
        (folder / "r2_read_coverage.py").write_text(_READER)

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

        dump = _uv().call(
            "run",
            *with_args,
            "python",
            str(folder / "r2_read_coverage.py"),
            str(data_file),
            str(root),
            _path=root,
        )
        if dump.returncode != 0:
            raise CollectError("could not read the coverage data", dump.stderr)
        return self._build(json.loads(dump.stdout), outcomes)

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


def _uv() -> CliTool:
    """
    The `uv` tool, echoing the commands it runs only at verbose level.
    """
    return replace(uv, echo=mode.verbosity >= VERBOSE)


def _report(line: str, progress: Progress | None) -> None:
    """
    Pass a progress marker line from the pytest plugin to `progress`.
    """
    if progress is None or not line.startswith(_MARKER):
        return
    event, _, rest = line.removeprefix(_MARKER).partition(" ")
    if event == "started":
        progress.started(int(rest))
    elif event == "finished":
        outcome, _, test_id = rest.partition(" ")
        progress.finished(test_id, cast(Outcome, outcome))


def _without_markers(output: str) -> str:
    """
    `output` without the plugin's progress marker lines.
    """
    return "".join(
        line
        for line in output.splitlines(keepends=True)
        if not line.startswith(_MARKER)
    )


def _relative(name: str, root: Path) -> str | None:
    """
    `name` as a posix path relative to `root`, or None when outside it.
    """
    try:
        return Path(name).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


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
