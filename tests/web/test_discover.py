from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from r2.web.discover import find_projects, register_found
from r2.web.registry import read_registry, register
from r2.web.settings import Settings
from tests.reports.repo import Repo


@pytest.fixture
def home(tmp_path: Path) -> Path:
    folder = tmp_path.resolve() / "tree"
    folder.mkdir()
    return folder


def project(home: Path, path: str, *, attached: bool = True) -> Path:
    """A project directory at `path`, attached unless told otherwise."""
    root = home / path
    (root / ".reportlab" / "reports").mkdir(parents=True)
    if attached:
        (root / ".reportlab" / "config.toml").write_text("[rl]\n")
    return root


def settings(
    home: Path, *, roots: list[Path] | None = None, depth: int = 6
) -> Settings:
    return Settings(roots=[home] if roots is None else roots, depth=depth)


class TestFindProjects:
    def test_finds_an_attached_project_under_a_root(self, home: Path) -> None:
        root = project(home, "work/api")
        assert find_projects(settings(home)) == [root]

    def test_ignores_a_reportlab_with_no_config_which_is_what_detached_means(
        self, home: Path
    ) -> None:
        project(home, "work/api", attached=False)
        assert find_projects(settings(home)) == []

    def test_does_nothing_without_roots(self, home: Path) -> None:
        project(home, "work/api")
        assert find_projects(settings(home, roots=[])) == []

    def test_stops_at_the_configured_depth(self, home: Path) -> None:
        project(home, "a/b/c/d/deep")
        assert find_projects(settings(home, depth=2)) == []
        assert len(find_projects(settings(home, depth=8))) == 1

    def test_finds_a_project_directly_in_the_root_at_depth_zero(
        self, home: Path
    ) -> None:
        project(home, ".")
        assert find_projects(settings(home, depth=0)) == [home]

    def test_does_not_walk_into_node_modules_or_dot_directories(
        self, home: Path
    ) -> None:
        project(home, "node_modules/package")
        project(home, ".hidden/thing")
        assert find_projects(settings(home)) == []

    def test_does_not_follow_a_symlink_so_a_loop_cannot_hang_it(
        self, home: Path
    ) -> None:
        root = project(home, "real")
        (home / "loop").symlink_to(home, target_is_directory=True)
        assert find_projects(settings(home)) == [root]

    def test_finds_several_and_reports_each_root_once(self, home: Path) -> None:
        a = project(home, "one")
        b = project(home, "two/nested")
        found = find_projects(settings(home, roots=[home, home]))
        assert sorted(found) == sorted([a, b])

    def test_survives_a_root_that_is_not_there(self, home: Path) -> None:
        assert find_projects(settings(home, roots=[home / "nope"])) == []


class TestRegisterFound:
    def test_registers_the_projects_it_finds_and_returns_them(self, home: Path) -> None:
        project(home, "work/api")
        added = register_found(settings(home))
        assert [p.name for p in added] == ["api"]
        assert [e.name for e in read_registry().projects] == ["api"]

    def test_does_not_add_a_project_twice(self, home: Path) -> None:
        project(home, "work/api")
        register_found(settings(home))
        assert register_found(settings(home)) == []
        assert len(read_registry().projects) == 1

    def test_skips_projects_that_are_already_registered(
        self, home: Path, make_repo: Callable[[str], Repo]
    ) -> None:
        known = make_repo("known")
        register(known.project)
        assert register_found(settings(home, roots=[known.root.parent])) == []

    def test_does_not_register_a_detached_project(self, home: Path) -> None:
        project(home, "work/api", attached=False)
        assert register_found(settings(home)) == []
        assert read_registry().projects == []

    def test_does_nothing_without_roots(self, home: Path) -> None:
        project(home, "work/api")
        assert register_found(settings(home, roots=[])) == []
        assert read_registry().projects == []
