from pathlib import Path

import pytest

from r2.core.tasks import get_project
from r2.core.tasks.pyproject import PyProject, parse_dependencies


def test_parse_dependencies() -> None:
    assert parse_dependencies(["a>=1.0", "b==2", "c", "d @ git+x"]) == {
        "a": "1.0",
        "b": "2",
        "c": "",
        "d": "git+x",
    }


def test_reads_tasks_and_dependencies(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\ndependencies = ["rich>=14"]\n'
        '[dependency-groups]\ndev = ["pytest>=8"]\n'
        '[tool.taskipy.tasks]\ntest = "pytest"\n'
    )
    project = get_project(tmp_path)
    assert isinstance(project, PyProject)
    assert project.tasks == {"test": "pytest"}
    assert project.any_dependencies == {"pytest": "8", "rich": "14"}


def test_directory_without_a_project_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        get_project(tmp_path)
