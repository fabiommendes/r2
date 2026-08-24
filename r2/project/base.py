from pathlib import Path
from typing import Literal, Protocol, get_args

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

    def test(self) -> None:
        """
        Run tests for the project.
        """
        raise NotImplementedError

    def build(self) -> None:
        """
        Build the project.
        """
        raise NotImplementedError

    def docs(self) -> None:
        """
        Generate documentation for the project.
        """
        raise NotImplementedError

    def run(self, script: str | None = None) -> None:
        """
        With an argument, run a script within the project.

        Without an argument, run the default entry point for the project.
        """
        if script is None:
            return self.run_default()
        else:
            return self.run_script(script)

    def run_default(self) -> None:
        """
        Run the default entry point for the project.
        """
        raise NotImplementedError

    def run_script(self, script: str) -> None:
        """
        Run a specific script within the project.
        """
        raise NotImplementedError
