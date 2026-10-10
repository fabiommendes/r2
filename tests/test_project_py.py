from pathlib import Path

import pytest

from r2.core.project import get_project
from r2.core.project.py import UvProject, parse_dependencies


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
    assert isinstance(project, UvProject)
    assert project.tasks == {"test": "pytest"}
    assert project.any_dependencies == {"pytest": "8", "rich": "14"}


def test_directory_without_a_project_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        get_project(tmp_path)


def test_parse_dependencies_drops_extras_and_markers() -> None:
    deps = ["a[x,y]>=1", "b ; python_version < '3.13'", "c~=1.4", "d>=1,<2"]
    assert parse_dependencies(deps) == {"a": "1", "b": "", "c": "~=1.4", "d": ">=1,<2"}


def test_unpinned_pytest_is_detected(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[dependency-groups]\ndev = ["pytest"]\n'
    )
    project = UvProject(tmp_path)
    assert "pytest" in project.any_dependencies


def test_init_refuses_an_existing_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    with pytest.raises(RuntimeError):
        UvProject.init(tmp_path, "lib")
