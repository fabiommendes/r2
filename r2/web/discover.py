"""
Finding attached projects under the roots the user configured.

What is looked for is `.reportlab/config.toml`, not `.reportlab/`: an agent
creates the folder by writing a report into it, so the folder alone does not
say anybody wants the project watched. There is no default root.
"""

from __future__ import annotations

import os
from pathlib import Path

from r2.core.reports.project import CONFIG, LAYOUT_DIR, Project, describe
from r2.web.registry import load_projects, register
from r2.web.settings import Settings

__all__ = ["find_projects", "register_found"]

#: Never worth walking into. Hidden folders are skipped too.
SKIP = frozenset(
    {
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "target",
        "venv",
        "vendor",
    }
)


def find_projects(settings: Settings) -> list[Path]:
    """
    Breadth first, up to `settings.depth` levels below each root.
    Symlinks are not followed, which keeps a loop from hanging the scan.
    """
    found: list[Path] = []
    level = list(dict.fromkeys(settings.roots))
    for _ in range(settings.depth + 1):
        if not level:
            break
        below: list[Path] = []
        for folder in level:
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name == LAYOUT_DIR:
                    if (Path(entry.path) / CONFIG).is_file():
                        found.append(folder)
                    continue
                if entry.name.startswith(".") or entry.name in SKIP:
                    continue
                below.append(Path(entry.path))
        level = below
    return found


def register_found(settings: Settings) -> list[Project]:
    """Register the attached projects found that are not registered yet."""
    if not settings.roots:
        return []
    known = {project.root for project in load_projects().projects}
    added: list[Project] = []
    for root in find_projects(settings):
        try:
            project = describe(root)
        except OSError:
            # It was there a moment ago. Nothing to recover.
            continue
        if project.attached and project.root not in known:
            register(project)
            added.append(project)
    return added
