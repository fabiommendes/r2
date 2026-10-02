from pathlib import Path

from r2.core.tasks.base import Project
from r2.core.tasks.pyproject import PyProject


def get_project(path: Path | None) -> Project:
    """
    Return the first compatible project entry in the given path (or CWD)/
    """

    path = path or Path.cwd()

    if PyProject.is_project(path):
        return PyProject(path)
    else:
        raise RuntimeError(f"Could not determine the project type at {path}")
