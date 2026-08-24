from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, assert_never

from .. import console
from ..cli_tool import CliTool
from .base import Project as BaseProject
from .base import ProjectKind

type Data = dict[str, Any]

uv = CliTool("uv")


@dataclass(frozen=True)
class PyProject(BaseProject):
    """
    Python projects using the `pyproject.toml` file for configuration.
    """

    root: Path
    data: Data = field(default_factory=dict)

    def __post_init__(self):
        if self.data == {}:
            with open(self.root / "pyproject.toml", "rb") as f:
                data = tomllib.load(f)
                object.__setattr__(self, "data", data)

    @classmethod
    def is_project(cls, path: Path) -> bool:
        return os.path.isfile(os.path.join(path, "pyproject.toml"))

    @classmethod
    def init(cls, path: Path, kind: ProjectKind) -> PyProject:
        if not cls.is_project(path):
            msg = f"Not a valid python project: pyproject.toml was not found in {path}"
            raise RuntimeError(msg)

        match kind:
            case "lib":
                uv.run("init", "--lib")
            case "cli" | "app":
                uv.run("init")
            case other:
                assert_never(other)

        return PyProject(path)

    @property
    def tasks(self) -> dict[str, str]:
        return self["tool.taskipy.tasks"] or {}

    def __getitem__(self, key: str) -> Any:
        parts = key.split(".")
        data = self.data
        try:
            for part in parts:
                data = data[part]
        except (KeyError, IndexError, TypeError):
            return None
        return data

    def _try_tasks(self, tasks: list[str]) -> None:
        """
        Try to run a task if it exists in the project and "exec" to it, leaving
        the current process.
        """
        for task in tasks:
            if task in self.tasks:
                uv.exec("run", "task", task)
                return

    def test(self):
        self._try_tasks(["test", "tests"])
        console.stderr.print("Could not find the test runner")

    def build(self) -> None:
        self._try_tasks(["test", "tests"])
        console.stderr.print("Could not find the project builder")

    def docs(self) -> None:
        self._try_tasks(["docs", "doc", "documentation"])
        console.stderr.print("Could not build the project documentation")

    def run_default(self) -> None:
        self._try_tasks(["run", "dev", "start", "main"])
        console.stderr.print("Could not find a default task to run")

    def run_script(self, script: str) -> None:
        self._try_tasks([script])
        console.stderr.print(f"Could not find a task named '{script}'")
