"""
Coverage map: the spans each test of one runner covers.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from r2.core.project.base import Project

from r2.core.files import atomic_write

type TestId = str
type SpanKind = Literal["arc", "region", "block", "line"]
type Outcome = Literal["passed", "failed", "skipped"]

RUNNERS: tuple[str, ...] = ("pytest", "nextest", "vitest", "playwright")
"""Runner names r2 knows. A selector prefix `name:` restricts it to one."""

COVERAGE_DIR = Path(".r2") / "coverage"
"""Where maps live, relative to the project root."""

_SPAN_RE = re.compile(r"(.+):(-?\d+):(\d+)-(-?\d+):(\d+)")


@dataclass(frozen=True, order=True)
class Span:
    """
    Smallest piece of code a runner tells apart, located in a source file.

    Its text form is `path:line:col-line:col`, with `path` relative to the
    project root. A line span has both columns 0 and the same start and end
    line. For arcs (coverage.py), `start_line` and `end_line` are the two
    ends of the arc and may be negative (entry/exit of a code object).
    """

    path: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    @classmethod
    def parse(cls, text: str) -> Span:
        """
        Parse the text form. Raise ValueError when it is malformed.
        """
        match = _SPAN_RE.fullmatch(text)
        if match is None:
            raise ValueError(f"malformed span: {text!r}")
        path, start_line, start_col, end_line, end_col = match.groups()
        return cls(path, int(start_line), int(start_col), int(end_line), int(end_col))

    @classmethod
    def line(cls, path: str, line: int) -> Span:
        """
        The line span of one line.
        """
        return cls(path, line, 0, line, 0)

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.start_line}:{self.start_col}"
            f"-{self.end_line}:{self.end_col}"
        )

    def to_lines(self, kind: SpanKind) -> frozenset[Span]:
        """
        The line spans this span reduces to.

        An arc reduces to the lines of its two ends (absolute value, ends at
        line 0 or below dropped). A region, block or line reduces to every
        line from start to end.
        """
        if kind == "arc":
            ends = {abs(self.start_line), abs(self.end_line)}
            return frozenset(self.line(self.path, n) for n in ends if n > 0)
        lines = range(self.start_line, self.end_line + 1)
        return frozenset(self.line(self.path, n) for n in lines)


@dataclass(frozen=True)
class TestRecord:
    __test__ = False  # not a pytest test class

    outcome: Outcome
    spans: frozenset[Span] = frozenset()


@dataclass(frozen=True)
class CoverageMap:
    """
    What one runner recorded for a project. Serialized as JSON to
    `.r2/coverage/<runner>.json` at the project root.
    """

    VERSION: ClassVar[int] = 1

    runner: str
    span_kind: SpanKind
    tests: Mapping[TestId, TestRecord] = field(default_factory=dict)
    ambient: frozenset[Span] = frozenset()
    files: Mapping[str, str] = field(default_factory=dict)
    """Measured source file (relative path) -> sha256 hex of its content."""
    created: str = ""
    """ISO 8601 timestamp."""
    commit: str | None = None
    dirty: bool = False

    def to_json(self) -> str:
        """
        Deterministic JSON text: keys, tests and spans sorted.
        """
        data = {
            "version": self.VERSION,
            "runner": self.runner,
            "span_kind": self.span_kind,
            "created": self.created,
            "commit": self.commit,
            "dirty": self.dirty,
            "files": dict(sorted(self.files.items())),
            "ambient": _span_strings(self.ambient),
            "tests": {
                test_id: {
                    "outcome": record.outcome,
                    "spans": _span_strings(record.spans),
                }
                for test_id, record in sorted(self.tests.items())
            },
        }
        return json.dumps(data, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> CoverageMap:
        """
        Inverse of `to_json`. Raise ValueError for a different `version`.
        """
        data = json.loads(text)
        if data.get("version") != cls.VERSION:
            raise ValueError(
                f"unsupported coverage map version: {data.get('version')!r}"
            )
        return cls(
            runner=data["runner"],
            span_kind=data["span_kind"],
            tests={
                test_id: TestRecord(
                    outcome=item["outcome"],
                    spans=frozenset(Span.parse(s) for s in item["spans"]),
                )
                for test_id, item in data["tests"].items()
            },
            ambient=frozenset(Span.parse(s) for s in data["ambient"]),
            files=dict(data["files"]),
            created=data["created"],
            commit=data["commit"],
            dirty=data["dirty"],
        )

    @staticmethod
    def path(root: Path, runner: str) -> Path:
        """
        Where the map of `runner` lives under the project `root`.
        """
        return root / COVERAGE_DIR / f"{runner}.json"

    def save(self, root: Path) -> Path:
        """
        Write the map atomically under `root` and return its path. Creates
        `.r2/.gitignore` holding `*` when it does not exist.
        """
        path = self.path(root, self.runner)
        path.parent.mkdir(parents=True, exist_ok=True)
        gitignore = root / ".r2" / ".gitignore"
        if not gitignore.exists():
            atomic_write(gitignore, "*\n")
        atomic_write(path, self.to_json())
        return path

    @classmethod
    def load(cls, root: Path, runner: str) -> CoverageMap:
        """
        Read the map of `runner`. Raise FileNotFoundError when missing.
        """
        return cls.from_json(cls.path(root, runner).read_text(encoding="utf-8"))

    def stale_files(self, root: Path) -> list[str]:
        """
        Measured files whose content changed or that no longer exist,
        sorted.
        """
        stale = []
        for name, digest in self.files.items():
            try:
                content = (root / name).read_bytes()
            except OSError:
                stale.append(name)
                continue
            if hashlib.sha256(content).hexdigest() != digest:
                stale.append(name)
        return sorted(stale)

    def merge(self, newer: CoverageMap, selectors: Sequence[str]) -> CoverageMap:
        """
        Apply a collect run made with `selectors` on top of this map.

        Tests matching the selectors are replaced by the ones in `newer`
        (and dropped if `newer` lacks them); the others are kept. Ambient
        spans, files, created, commit and dirty come from `newer`. With no
        selectors, the result is `newer`.
        """
        if not selectors:
            return newer
        runner = self.runner
        tests = {
            test_id: record
            for test_id, record in self.tests.items()
            if not matches(selectors, runner, test_id)
        }
        tests.update(
            (test_id, record)
            for test_id, record in newer.tests.items()
            if matches(selectors, runner, test_id)
        )
        return replace(newer, tests=tests)


def matches(selectors: Sequence[str], runner: str, test: TestId) -> bool:
    """
    Whether any selector picks `test` of `runner`.

    A selector is a glob matched against the whole test id, or the exact
    id. A prefix `name:` where `name` is in RUNNERS restricts it to that
    runner; any other text before a colon is part of the glob (pytest ids
    hold `::`). No selectors pick nothing.
    """
    return any(_selects(selector, runner, test) for selector in selectors)


def _selects(selector: str, runner: str, test: TestId) -> bool:
    """
    Whether one selector picks `test` of `runner`.
    """
    if selector == test:
        return True
    prefix, colon, rest = selector.partition(":")
    if colon and prefix in RUNNERS:
        if prefix != runner:
            return False
        selector = rest
        if selector == test:
            return True
    return fnmatchcase(test, selector)


def _span_strings(spans: frozenset[Span]) -> list[str]:
    """
    The text form of `spans`, sorted.
    """
    return sorted(str(span) for span in spans)


@dataclass(frozen=True)
class MissingTool:
    """
    An external program a runner needs and could not find.
    """

    name: str
    install: str
    """Command or instruction that installs it."""


class CollectError(Exception):
    """
    The runner could not run at all: build error, no tests collected...

    Test failures are not collect errors.
    """

    def __init__(self, message: str, output: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.output = output
        """The runner's combined output, for the caller to show a tail of."""


class CoverageRunner(ABC):
    """
    A test tool r2 knows how to instrument for per-test coverage.
    """

    name: ClassVar[str]
    span_kind: ClassVar[SpanKind]

    def __init__(self, project: Project) -> None:
        self.project = project

    @classmethod
    @abstractmethod
    def detect(cls, project: Project) -> bool:
        """
        Whether `project` uses this runner.
        """

    @abstractmethod
    def missing_tools(self) -> list[MissingTool]:
        """
        External programs needed by `collect` that are not available.
        """

    @abstractmethod
    def collect(self, selectors: Sequence[str] = ()) -> CoverageMap:
        """
        Run the tests picked by `selectors` (every test without selectors)
        under instrumentation and return their map. Never changes the
        project's files; scratch files go under `.r2/coverage/`. Raise
        CollectError when the runner could not run.
        """
