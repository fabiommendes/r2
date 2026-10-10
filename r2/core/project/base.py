from __future__ import annotations

from pathlib import Path
from typing import Literal, Never, Protocol, Self, get_args

ProjectKind = Literal["lib", "cli", "app"]

PROJECT_KINDS: list[str] = list(get_args(ProjectKind))


class Project(Protocol):
    @classmethod
    def is_project(cls, path: Path) -> bool:
        """
        Verify if the given path is a valid project directory for this type of project.
        """
        raise NotImplementedError

    @classmethod
    def init[T](cls: T, path: Path, kind: ProjectKind) -> T:
        """
        Initialize a new project at the given path.
        """
        raise NotImplementedError

    def test(self) -> Never:
        """
        Run tests for the project.
        """
        raise NotImplementedError

    def build(self) -> Never:
        """
        Build the project.
        """
        raise NotImplementedError

    def docs(self) -> Never:
        """
        Generate documentation for the project.
        """
        raise NotImplementedError

    def run(self, script: str | None = None) -> Never:
        """
        With an argument, run a script within the project.

        Without an argument, run the default entry point for the project.
        """
        if script is None:
            self.run_default()
        else:
            self.run_task(script)

    def run_default(self) -> Never:
        """
        Run the default entry point for the project.
        """
        raise NotImplementedError

    def run_task(self, script: str) -> Never:
        """
        Run a specific script within the project.
        """
        raise NotImplementedError

    def run_subcommand(self, command: list[str]) -> Never:
        exit(0)


class NoOpProject(Project):
    """
    Base implementation that is a no-op for all methods.
    """

    @classmethod
    def is_project(cls, path: Path) -> bool:
        return False

    @classmethod
    def init(cls, path: Path, kind: ProjectKind) -> Self:
        return cls()

    def test(self) -> Never:
        exit(0)

    def build(self) -> Never:
        exit(0)

    def docs(self) -> Never:
        exit(0)

    def run_default(self) -> Never:
        exit(0)

    def run_task(self, script: str) -> Never:
        exit(0)

    def run_subcommand(self, command: list[str]) -> Never:
        exit(0)
