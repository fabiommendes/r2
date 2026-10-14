"""
Where a project keeps its stories and e2e tests, and the checks that tie the
two together. See dev/spec/stories.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from r2.core.plugins.discovery import discover_project
from r2.core.r2_context import find_root
from r2.core.stories.doc import Story, StoryFile, is_strict, parse
from r2.core.stories.tests import StoryTest, find_tests

__all__ = [
    "Layout",
    "Problem",
    "Report",
    "StoryRef",
    "check",
    "layout",
    "load",
    "project_root",
    "run",
    "story_paths",
]

STORIES_DIR = Path("docs") / "user-stories"
TESTS_DIRS = (Path("test") / "stories", Path("tests") / "stories")
"""The e2e test folders used when none is configured: the first that exists."""
SKIPPED_FILES = {"readme.md", "coverage.md"}
CONFIG_KEY = "stories"
PROJECT_FILES = ("pyproject.toml", "Cargo.toml", "package.json")

type Kind = Literal[
    "duplicate-id",
    "duplicate-role",
    "untested",
    "no-story",
    "unknown-story",
    "several-tests",
    "unbuilt-story",
]


@dataclass(frozen=True)
class Layout:
    root: Path
    stories: Path
    """The folder with one story file per role."""
    tests: list[Path]
    """The files and folders with the e2e tests."""


def project_root(start: Path) -> Path:
    """
    The closest folder, from start up, with a project file r2 knows
    (`pyproject.toml`, `Cargo.toml`, `package.json`), as in `r2 coverage`;
    without one, the git root or start itself.
    """
    for folder in (start, *start.parents):
        if any((folder / name).is_file() for name in PROJECT_FILES):
            return folder
    return find_root(start)


def layout(
    start: Path, stories: Path | None = None, tests: Sequence[Path] = ()
) -> Layout:
    """
    The layout of the project at start. Paths given here win over
    `[config.stories]` in the project manifest (`dir`, `tests`), which wins
    over the defaults.
    """
    root = project_root(start.resolve())
    plugin, _ = discover_project(root)
    config: dict[str, Any] = {}
    base = root
    if plugin is not None:
        config = plugin.config.get(CONFIG_KEY, {})
        base = plugin.root

    folder = stories
    if folder is None:
        folder = base / str(config["dir"]) if "dir" in config else root / STORIES_DIR
    test_paths = list(tests)
    if not test_paths and "tests" in config:
        configured = config["tests"]
        names = [configured] if isinstance(configured, str) else list(configured)
        test_paths = [base / str(name) for name in names]
    if not test_paths:
        test_paths = [root / path for path in TESTS_DIRS if (root / path).is_dir()][:1]
    return Layout(root=root, stories=folder, tests=test_paths)


def story_paths(folder: Path) -> list[Path]:
    """
    The story files in folder: every `.md` file but README.md and
    coverage.md, unless they declare `type: stories`.
    """
    if not folder.is_dir():
        return []
    return [
        path
        for path in sorted(folder.glob("*.md"))
        if path.name.lower() not in SKIPPED_FILES or is_strict(_read(path))
    ]


def load(folder: Path) -> dict[Path, StoryFile]:
    """The story files in folder, by path."""
    return {path: parse(_read(path), path.stem) for path in story_paths(folder)}


@dataclass(frozen=True)
class StoryRef:
    """A story with where it was found."""

    path: Path
    role: str
    section: str
    story: Story

    @property
    def id(self) -> str:
        return f"{self.role}: {self.story.slug}"


@dataclass(frozen=True)
class Problem:
    kind: Kind
    subject: str
    """The story id, test location or file the problem is about."""
    message: str

    def __str__(self) -> str:
        return f"{self.subject}: {self.message}"


@dataclass
class Report:
    stories: list[StoryRef]
    tests: list[StoryTest]
    tests_of: dict[str, list[StoryTest]] = field(default_factory=dict)
    """The tests that cite each story, by story id."""
    errors: list[Problem] = field(default_factory=list)
    warnings: list[Problem] = field(default_factory=list)

    def missing(self) -> list[StoryRef]:
        """The stories no test cites."""
        return [ref for ref in self.stories if not self.tests_of.get(ref.id)]

    def covered(self) -> list[StoryRef]:
        """The stories some test cites."""
        return [ref for ref in self.stories if self.tests_of.get(ref.id)]

    def stale(self) -> list[StoryTest]:
        """The tests that cite no story, or one that does not exist."""
        return [
            test
            for test in self.tests
            if test.story is None or test.story not in self.tests_of
        ]

    def coverage(self) -> list[dict[str, Any]]:
        """Per role: how many stories, how many have a test, how many need one."""
        roles: dict[str, dict[str, Any]] = {}
        for ref in self.stories:
            row = roles.setdefault(
                ref.role, {"role": ref.role, "stories": 0, "tested": 0, "need_test": 0}
            )
            row["stories"] += 1
            row["tested"] += bool(self.tests_of.get(ref.id))
            row["need_test"] += ref.story.needs_test
        return list(roles.values())


def check(
    files: dict[Path, StoryFile],
    tests: list[StoryTest],
    root: Path,
    no_duplicates: bool = False,
) -> Report:
    """
    Match the stories in files with the tests and report what is wrong.

    Errors: two stories with the same id, two files with the same role, an
    implemented or partial story without a test, a test that cites no story
    or one that does not exist, and with no_duplicates a story with more
    than one test. Warnings: a test of a todo or deprecated story.
    """
    report = Report(stories=[], tests=tests)
    roles: dict[str, Path] = {}
    for path, doc in files.items():
        where = _relative(path, root)
        if doc.role in roles:
            other = _relative(roles[doc.role], root)
            report.errors.append(
                Problem("duplicate-role", where, f"role {doc.role!r} is also {other}")
            )
            continue
        roles[doc.role] = path
        seen: dict[str, Story] = {}
        for section in doc.sections:
            for story in section.stories:
                ref = StoryRef(path, doc.role, section.name, story)
                if story.slug in seen:
                    first = seen[story.slug].title
                    report.errors.append(
                        Problem(
                            "duplicate-id",
                            where,
                            f"{story.title!r} and {first!r} share the id {ref.id}",
                        )
                    )
                    continue
                seen[story.slug] = story
                report.stories.append(ref)
                report.tests_of[ref.id] = []

    for test in tests:
        if test.story is None:
            report.errors.append(
                Problem("no-story", test.location, f"{test.name!r} cites no story")
            )
        elif test.story not in report.tests_of:
            report.errors.append(
                Problem(
                    "unknown-story",
                    test.location,
                    f"{test.cites!r} cites no existing story",
                )
            )
        else:
            report.tests_of[test.story].append(test)

    for ref in report.stories:
        cited = report.tests_of[ref.id]
        status = ref.story.status
        if ref.story.needs_test and not cited:
            report.errors.append(
                Problem("untested", ref.id, f"has no test (status: {status})")
            )
        if not ref.story.needs_test:
            report.warnings += [
                Problem("unbuilt-story", test.location, f"tests a {status} story")
                for test in cited
            ]
        if no_duplicates and len(cited) > 1:
            where = ", ".join(test.location for test in cited)
            report.errors.append(
                Problem("several-tests", ref.id, f"has {len(cited)} tests: {where}")
            )
    return report


def run(layout: Layout, no_duplicates: bool = False) -> Report:
    """Load the stories and tests of layout and check them."""
    tests = find_tests(layout.root, layout.tests)
    return check(load(layout.stories), tests, layout.root, no_duplicates)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")
