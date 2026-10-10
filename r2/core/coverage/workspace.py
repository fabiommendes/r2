"""
Coverage maps of one project on disk: finding the project, its runners and
its maps. The glue between the runners, the maps and the CLI.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

from r2.core.coverage.base import RUNNERS, CoverageMap, CoverageRunner
from r2.core.coverage.py import PytestCoverage
from r2.core.project.base import Project
from r2.core.project.py import UvProject

RUNNER_CLASSES: tuple[type[CoverageRunner], ...] = (PytestCoverage,)
"""Runner classes r2 knows, in RUNNERS order."""

PROJECT_FILES = ("pyproject.toml", "Cargo.toml", "package.json")


class _Rooted(Protocol):
    root: Path


def find_project_root(start: Path) -> Path:
    """
    The closest folder, from `start` up, that holds a project r2 knows
    (`pyproject.toml`, `Cargo.toml`, `package.json`). Raise
    FileNotFoundError when there is none.
    """
    for folder in (start, *start.parents):
        if any((folder / name).is_file() for name in PROJECT_FILES):
            return folder
    raise FileNotFoundError(f"no project found from {start}")


def detect_runners(root: Path, names: Sequence[str] = ()) -> list[CoverageRunner]:
    """
    The runners the project at `root` uses, in RUNNERS order. With `names`,
    only those; a name that is not detected raises ValueError.
    """
    projects = _projects(root)
    runners = [
        cls(project)
        for cls in RUNNER_CLASSES
        for project in projects
        if cls.detect(project)
    ]
    found = {runner.name for runner in runners}
    for name in names:
        if name not in found:
            raise ValueError(f"runner {name!r} not detected in {root}")
    return [runner for runner in runners if not names or runner.name in names]


def collect(runner: CoverageRunner, selectors: Sequence[str] = ()) -> CoverageMap:
    """
    Run `runner.collect(selectors)`, merge the result into the saved map of
    that runner (`CoverageMap.merge`), save it and return it. Without a
    saved map, the result is saved as is.
    """
    root = cast(_Rooted, runner.project).root
    new = runner.collect(selectors)
    try:
        saved = CoverageMap.load(root, runner.name).merge(new, selectors)
    except FileNotFoundError:
        saved = new
    saved.save(root)
    return saved


def load_maps(root: Path, names: Sequence[str] = ()) -> list[CoverageMap]:
    """
    The saved maps under `root`, sorted by runner; with `names`, only those.
    Raise FileNotFoundError when there is no map at all, or a named one is
    missing.
    """
    wanted = list(names) or [
        runner for runner in RUNNERS if CoverageMap.path(root, runner).is_file()
    ]
    if not wanted:
        raise FileNotFoundError(f"no coverage map under {root}")
    return sorted(
        (CoverageMap.load(root, runner) for runner in wanted),
        key=lambda cmap: cmap.runner,
    )


def _projects(root: Path) -> list[Project]:
    """
    The projects the files at `root` describe.
    """
    projects: list[Project] = []
    if UvProject.is_project(root):
        projects.append(UvProject(root))
    return projects
