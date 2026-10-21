"""
A project as the report viewer sees it: a repository root and its
`.reportlab/` directory.

What attaches a project is `.reportlab/config.toml`, not `.reportlab/`: an
agent creates the directory by writing a report into it, so the directory
alone proves nothing. `[rl] name` is a label for the UI and never feeds the
project id.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "CONFIG",
    "LAYOUT_DIR",
    "REPORT_SUFFIX",
    "REVIEW_SUFFIX",
    "TEMPLATE",
    "DetachResult",
    "Project",
    "ProjectConfig",
    "describe",
    "detach_project",
    "ensure_layout",
    "find_project",
    "read_project_config",
]

LAYOUT_DIR = ".reportlab"
CONFIG = "config.toml"
REPORTS = "reports"
REPORT_SUFFIX = ".md"
#: Suffix of the sidecar holding a report's review marks.
REVIEW_SUFFIX = ".review.json"

#: What `r2 web init` writes. Every setting is commented out; presence is
#: the point.
TEMPLATE = """\
# r2 watches this project because this file is here.
# Run `r2 web detach` to stop, or delete the file.

[rl]
# name = "a better name than the directory"
"""

# Reports are throwaway and the index is a cache. Everything is ignored,
# with no exemptions: a team that wants to share the config commits it once
# with `git add -f`, and git keeps tracking a file it already tracks.
IGNORE = "# Reports are throwaway and the index is a cache.\n*\n"


@dataclass(frozen=True)
class ProjectConfig:
    """
    `.reportlab/config.toml`, the one file in `.reportlab/` a human writes.

    Read leniently: never raises, and unknown keys are left alone. A file
    that cannot be parsed still attaches the project, and `error` says why
    its contents were ignored, because a human wrote it and is waiting for
    something to change.
    """

    present: bool
    name: str | None = None
    error: str | None = None


def read_project_config(reportlab: Path) -> ProjectConfig:
    try:
        text = (reportlab / CONFIG).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ProjectConfig(present=False)
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        return ProjectConfig(present=True, error=f"{CONFIG} is not valid TOML: {error}")
    section = parsed.get("rl")
    if not isinstance(section, dict):
        return ProjectConfig(present=True)
    name = section.get("name")
    if name is None:
        return ProjectConfig(present=True)
    if not isinstance(name, str):
        return ProjectConfig(
            present=True, error=f"{CONFIG}: [rl] name must be a string"
        )
    return ProjectConfig(present=True, name=name.strip() or None)


@dataclass(frozen=True)
class Project:
    #: Directory name plus a short hash of the real path.
    id: str
    #: From `[rl] name` in the config, or the directory name.
    name: str
    #: Repository root, resolved.
    root: Path
    #: `.reportlab/config.toml` is there: the daemon watches this project.
    attached: bool
    #: Why the config contents were ignored.
    config_error: str | None = None

    @property
    def reportlab(self) -> Path:
        return self.root / LAYOUT_DIR

    @property
    def reports(self) -> Path:
        return self.reportlab / REPORTS


def find_project(start: Path) -> Project:
    """
    Walk up looking for `.git`. A directory with no repository is still a
    valid project, rooted where the search started: `.git` is read to find
    the root and for nothing else.
    """
    begin = start.resolve(strict=True)
    for folder in (begin, *begin.parents):
        if (folder / ".git").exists():
            return describe(folder)
    return describe(begin)


def describe(root: Path) -> Project:
    """
    Describe the project at root. Raises OSError when root is gone.

    The id comes from the directory name and never from the configured
    name: a display name is a thing people change, and an id is in every URL
    and in the registry.
    """
    real = root.resolve(strict=True)
    directory = real.name or str(real)
    digest = hashlib.sha256(str(real).encode()).hexdigest()[:8]
    config = read_project_config(real / LAYOUT_DIR)
    return Project(
        id=f"{_slug(directory)}-{digest}",
        name=config.name or directory,
        root=real,
        attached=config.present,
        config_error=config.error,
    )


def ensure_layout(project: Project) -> None:
    """
    Create the directories and make `.reportlab/` ignore itself, so the
    user's own ignore file is never touched. The config file, which attaches
    the project, is written last, so a half created layout never looks
    attached.
    """
    project.reports.mkdir(parents=True, exist_ok=True)
    ignore = project.reportlab / ".gitignore"
    if not ignore.exists():
        ignore.write_text(IGNORE, encoding="utf-8")
    config = project.reportlab / CONFIG
    if not config.exists():
        config.write_text(TEMPLATE, encoding="utf-8")


@dataclass(frozen=True)
class DetachResult:
    #: The config file was there and is gone now.
    detached: bool
    #: Reports deleted, when purging.
    reports: int = 0
    #: `.reportlab/` itself was removed.
    purged: bool = False


def detach_project(project: Project, *, purge: bool = False) -> DetachResult:
    """
    Stop watching a project.

    Deleting `config.toml` is the whole of it: the reports stay, and
    re-attaching is `r2 web init`. `purge` removes `.reportlab/` outright,
    which deletes the reports in it.
    """
    config = project.reportlab / CONFIG
    detached = config.exists()
    if not purge:
        config.unlink(missing_ok=True)
        return DetachResult(detached=detached)
    count = sum(
        1 for path in project.reports.rglob(f"*{REPORT_SUFFIX}") if path.is_file()
    )
    shutil.rmtree(project.reportlab, ignore_errors=True)
    return DetachResult(detached=detached, reports=count, purged=True)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
