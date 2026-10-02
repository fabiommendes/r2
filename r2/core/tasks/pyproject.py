from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Never, assert_never

from r2.core import console
from r2.core.cli_tool import CliTool
from r2.core.tasks.base import Project as BaseProject
from r2.core.tasks.base import ProjectKind

type Data = dict[str, Any]
type Manager = Literal["uv"]

uv = CliTool("uv")


@dataclass(frozen=True)
class PyProject(BaseProject):
    """
    Python projects using the `pyproject.toml` file for configuration.
    """

    root: Path
    data: Data = field(default_factory=dict)

    def __post_init__(self) -> None:
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

    @property
    def dependencies(self) -> dict[str, str]:
        return parse_dependencies(self["project.dependencies"] or [])

    @property
    def dev_dependencies(self) -> dict[str, str]:
        return parse_dependencies(self["dependency-groups.dev"] or [])

    @property
    def any_dependencies(self) -> dict[str, str]:
        return self.dev_dependencies | self.dependencies

    @property
    def manager(self) -> Manager:
        return "uv"  # Only uv is supported for now!

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
                self.run_subcommand(["task", task])
                return

    def test(self) -> Never:
        self._try_tasks(["test", "tests"])

        # Try pytest run
        if self.dev_dependencies.get("pytest"):
            uv.exec("run", "pytest", _path=self.root)
        fail("Could not find the test runner")

    def install(self) -> Never:
        self._try_tasks(["install", "configure"])

        match self.manager:
            case "uv":
                uv.exec("sync", _path=self.root)
            case other:
                assert_never(other)

    def build(self) -> Never:
        self._try_tasks(["build", "builds"])

        match self.manager:
            case "uv":
                uv.exec("build", _path=self.root)
            case other:
                assert_never(other)

    def docs(self) -> Never:
        self._try_tasks(["docs", "doc", "documentation"])

        # If doc0 is installed, use it.
        if "doc-zero" in self.any_dependencies:
            uv.exec("run", "doc-zero", "build", _path=self.root)

        fail("Could not build the project documentation")

    def run_default(self) -> Never:
        self._try_tasks(["run", "dev", "start", "main"])
        fail("Could not find a default task to run")

    def run_task(self, script: str) -> Never:
        self._try_tasks([script])
        fail(f"Could not find a task named '{script}'")

    def run_subcommand(self, command: list[str]) -> Never:
        match self.manager:
            case "uv":
                uv.exec("run", *command, _path=self.root)
            case other:
                assert_never(other)


def fail(msg: str) -> Never:
    console.stderr.print(msg)
    raise SystemExit(1)


def parse_dependencies(deps: list[str]) -> dict[str, str]:
    """
    Parse a list of dependency strings into a dictionary of {name: version}.
    """
    result: dict[str, str] = {}
    for dep in deps:
        if "@" in dep:
            name, version = dep.split("@", 1)
        elif ">=" in dep:
            name, version = dep.split(">=", 1)
        elif "==" in dep:
            name, version = dep.split("==", 1)
        else:
            name, version = dep, ""
        result[name.strip()] = version.strip()
    return result
