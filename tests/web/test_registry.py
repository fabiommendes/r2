from __future__ import annotations

import shutil
from collections.abc import Callable

from r2.core.reports.project import detach_project
from r2.web.paths import registry_file
from r2.web.registry import (
    Registry,
    RegistryEntry,
    load_projects,
    read_registry,
    register,
    unregister,
    write_registry,
)
from tests.reports.repo import Repo

type MakeRepo = Callable[[str], Repo]


def names(registry: Registry) -> list[str]:
    return [entry.name for entry in registry.projects]


class TestRegisterAndUnregister:
    def test_adds_a_project_and_puts_the_newest_first(
        self, make_repo: MakeRepo
    ) -> None:
        register(make_repo("one").project)
        register(make_repo("two").project)
        assert names(read_registry()) == ["two", "one"]

    def test_refreshes_rather_than_duplicating(self, make_repo: MakeRepo) -> None:
        only = make_repo("one").project
        register(only)
        register(only)
        assert len(read_registry().projects) == 1

    def test_refreshing_moves_the_project_to_the_front(
        self, make_repo: MakeRepo
    ) -> None:
        one = make_repo("one").project
        register(one)
        register(make_repo("two").project)
        register(one)
        assert names(read_registry()) == ["one", "two"]

    def test_records_the_id_and_the_root(self, make_repo: MakeRepo) -> None:
        project = make_repo("one").project
        register(project)
        [entry] = read_registry().projects
        assert (entry.id, entry.root) == (project.id, str(project.root))

    def test_lives_under_the_state_directory(
        self, make_repo: MakeRepo, machine_state: object
    ) -> None:
        register(make_repo("one").project)
        assert registry_file().is_file()
        assert registry_file().parts[-3:] == ("r2", "web", "projects.json")

    def test_removes_a_project(self, make_repo: MakeRepo) -> None:
        only = make_repo("one").project
        register(only)
        assert unregister(only.id)
        assert read_registry().projects == []

    def test_is_not_an_error_to_remove_one_that_is_not_there(self) -> None:
        assert not unregister("never-registered")


class TestReadRegistry:
    def test_no_file_is_an_empty_registry(self) -> None:
        assert read_registry() == Registry()

    def test_a_corrupt_file_is_an_empty_registry(self) -> None:
        registry_file().parent.mkdir(parents=True)
        registry_file().write_text("{ not json")
        assert read_registry() == Registry()

    def test_a_file_of_the_wrong_shape_is_an_empty_registry(self) -> None:
        registry_file().parent.mkdir(parents=True)
        registry_file().write_text('{"projects": 3}')
        assert read_registry() == Registry()

    def test_skips_an_entry_that_is_malformed(self, make_repo: MakeRepo) -> None:
        project = make_repo("one").project
        register(project)
        text = registry_file().read_text()
        registry_file().write_text(
            text.replace('"projects": [', '"projects": [{"id": 1}, 7, ', 1)
        )
        assert names(read_registry()) == ["one"]


class TestLoadProjects:
    def test_loads_what_is_there(self, make_repo: MakeRepo) -> None:
        register(make_repo("one").project)
        loaded = load_projects()
        assert [p.name for p in loaded.projects] == ["one"]
        assert loaded.removed == []
        assert all(p.attached for p in loaded.projects)

    def test_forgets_a_project_whose_directory_is_gone_and_writes_that_back(
        self, make_repo: MakeRepo
    ) -> None:
        kept = make_repo("kept")
        gone = make_repo("gone")
        register(kept.project)
        register(gone.project)
        shutil.rmtree(gone.root)

        loaded = load_projects()
        assert [p.name for p in loaded.projects] == ["kept"]
        assert [e.name for e in loaded.removed] == ["gone"]
        assert names(read_registry()) == ["kept"]

    def test_leaves_the_file_alone_when_nothing_is_missing(
        self, make_repo: MakeRepo
    ) -> None:
        register(make_repo("one").project)
        before = registry_file().read_bytes()
        load_projects()
        assert registry_file().read_bytes() == before

    def test_forgets_a_project_that_was_detached_and_writes_that_back(
        self, make_repo: MakeRepo
    ) -> None:
        kept = make_repo("kept")
        loose = make_repo("loose")
        register(kept.project)
        register(loose.project)
        detach_project(loose.project)

        loaded = load_projects()
        assert [p.name for p in loaded.projects] == ["kept"]
        assert [e.name for e in loaded.removed] == ["loose"]
        assert names(read_registry()) == ["kept"]
        assert loose.project.reports.is_dir()

    def test_survives_a_registry_of_nonsense(self) -> None:
        write_registry(
            Registry(projects=[RegistryEntry(id="x", name="x", root="/nowhere/at/all")])
        )
        loaded = load_projects()
        assert loaded.projects == []
        assert len(loaded.removed) == 1

    def test_picks_up_a_renamed_project_name(self, make_repo: MakeRepo) -> None:
        repo = make_repo("one")
        register(repo.project)
        (repo.project.reportlab / "config.toml").write_text('[rl]\nname = "Better"\n')
        assert [p.name for p in load_projects().projects] == ["Better"]
