from pathlib import Path

from .base import Project
from .pyproject import PyProject


def get_project(path: Path | None) -> Project:
    """
    Return the first compatible project entry in the given path (or CWD)/
    """

    path = path or Path.cwd()

    if PyProject.is_project(path):
        return PyProject(path)
    else:
        raise RuntimeError(f"Could not determine the project type at {path}")
