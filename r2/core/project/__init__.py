from pathlib import Path

from r2.core.project.base import Project
from r2.core.project.context import ProjectContext, Projects, find_root
from r2.core.project.py import UvProject

__all__ = [
    "Project",
    "ProjectContext",
    "Projects",
    "UvProject",
    "find_root",
    "get_project",
]


def get_project(path: Path | None) -> Project:
    """
    Return the first compatible project entry in the given path (or CWD).
    """

    path = path or Path.cwd()

    if UvProject.is_project(path):
        return UvProject(path)
    else:
        raise RuntimeError(f"Could not determine the project type at {path}")
