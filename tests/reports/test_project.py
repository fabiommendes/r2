from __future__ import annotations

from pathlib import Path

import pytest

from r2.core.reports.project import (
    CONFIG,
    DetachResult,
    ProjectConfig,
    describe,
    detach_project,
    ensure_layout,
    find_project,
    read_project_config,
)
from tests.reports.repo import Repo


def write_config(repo: Repo, text: str) -> None:
    (repo.project.reportlab / CONFIG).write_text(text)


class TestReadProjectConfig:
    def test_reads_a_name(self, repo: Repo) -> None:
        write_config(repo, '[rl]\nname = "auth service"\n')
        assert read_project_config(repo.project.reportlab) == ProjectConfig(
            present=True, name="auth service"
        )

    def test_reports_a_missing_file_which_is_what_detached_means(
        self, repo: Repo
    ) -> None:
        (repo.project.reportlab / CONFIG).unlink()
        assert read_project_config(repo.project.reportlab) == ProjectConfig(
            present=False
        )

    def test_leaves_unknown_keys_and_sections_alone(self, repo: Repo) -> None:
        write_config(
            repo, '[rl]\nname = "kept"\nfuture = 3\n\n[something.else]\nx = true\n'
        )
        assert read_project_config(repo.project.reportlab) == ProjectConfig(
            present=True, name="kept"
        )

    def test_reports_invalid_toml_instead_of_failing_quietly(self, repo: Repo) -> None:
        write_config(repo, "[rl\nname =\n")
        config = read_project_config(repo.project.reportlab)
        assert config.present
        assert config.name is None
        assert config.error is not None
        assert "not valid TOML" in config.error

    def test_reports_a_name_that_is_not_a_string(self, repo: Repo) -> None:
        write_config(repo, "[rl]\nname = 7\n")
        config = read_project_config(repo.project.reportlab)
        assert config.error is not None
        assert "must be a string" in config.error

    def test_a_config_that_cannot_be_decoded_does_not_raise(self, repo: Repo) -> None:
        (repo.project.reportlab / CONFIG).write_bytes(b"\xff\xfe[rl]\n")
        assert not read_project_config(repo.project.reportlab).present

    @pytest.mark.parametrize(
        "text",
        ['[rl]\nname = "  "\n', "[rl]\n", '[other]\nname = "no"\n', ""],
        ids=["blank name", "empty section", "other section", "empty file"],
    )
    def test_ignores_content_but_stays_attached(self, repo: Repo, text: str) -> None:
        write_config(repo, text)
        assert read_project_config(repo.project.reportlab) == ProjectConfig(
            present=True
        )


class TestDescribe:
    def test_uses_the_configured_name(self, repo: Repo) -> None:
        write_config(repo, '[rl]\nname = "auth service"\n')
        assert describe(repo.root).name == "auth service"

    def test_keeps_the_id_when_the_name_is_overridden(self, repo: Repo) -> None:
        before = describe(repo.root)
        write_config(repo, '[rl]\nname = "something entirely different"\n')
        after = describe(repo.root)
        assert after.id == before.id
        assert after.name != before.name

    def test_carries_the_config_error(self, repo: Repo) -> None:
        write_config(repo, "[rl\n")
        error = describe(repo.root).config_error
        assert error is not None
        assert "not valid TOML" in error

    def test_falls_back_to_the_directory_name(self, repo: Repo) -> None:
        write_config(repo, "[rl]\n")
        project = describe(repo.root)
        assert project.config_error is None
        assert project.name == "repo"

    def test_is_attached_when_the_config_is_there_and_not_when_it_is_not(
        self, repo: Repo
    ) -> None:
        assert describe(repo.root).attached
        (repo.project.reportlab / CONFIG).unlink()
        assert not describe(repo.root).attached

    def test_stays_attached_when_the_config_cannot_be_parsed(self, repo: Repo) -> None:
        write_config(repo, "[rl\n")
        assert describe(repo.root).attached

    def test_id_is_the_slugged_directory_name_and_a_short_hash(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "My Proj_X"
        root.mkdir()
        project_id = describe(root).id
        slug, _, digest = project_id.rpartition("-")
        assert slug == "my-proj-x"
        assert len(digest) == 8
        assert int(digest, 16) >= 0

    def test_same_name_in_different_places_gets_different_ids(
        self, tmp_path: Path
    ) -> None:
        first = tmp_path / "a" / "api"
        second = tmp_path / "b" / "api"
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        assert describe(first).id != describe(second).id

    def test_fails_when_the_root_is_gone(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            describe(tmp_path / "gone")


class TestFindProject:
    def test_walks_up_to_the_repository_root(self, repo: Repo) -> None:
        deep = repo.root / "src" / "pkg"
        deep.mkdir(parents=True)
        assert find_project(deep).root == repo.root

    def test_a_directory_without_a_repository_is_its_own_project(
        self, tmp_path: Path
    ) -> None:
        start = (tmp_path / "plain").resolve()
        start.mkdir()
        assert find_project(start).root == start

    def test_fails_when_the_start_is_gone(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            find_project(tmp_path / "gone")


class TestDetachProject:
    def test_deletes_the_config_and_leaves_everything_else(self, repo: Repo) -> None:
        repo.write_report("auth", "# Auth\n")
        result = detach_project(repo.project)
        assert result == DetachResult(detached=True, reports=0, purged=False)
        assert not describe(repo.root).attached
        assert [p.name for p in repo.project.reports.iterdir()] == ["auth.md"]

    def test_says_so_when_there_was_nothing_to_detach(self, repo: Repo) -> None:
        detach_project(repo.project)
        assert not detach_project(repo.project).detached

    def test_purges_the_whole_directory_and_counts_the_reports(
        self, repo: Repo
    ) -> None:
        repo.write_report("auth", "# Auth\n")
        repo.write_report("group/other", "# Other\n")
        result = detach_project(repo.project, purge=True)
        assert result == DetachResult(detached=True, reports=2, purged=True)
        assert not repo.project.reportlab.exists()

    def test_purge_does_not_touch_the_rest_of_the_repository(self, repo: Repo) -> None:
        source = repo.write_file("src/a.py", "x = 1\n")
        detach_project(repo.project, purge=True)
        assert source.read_text() == "x = 1\n"


class TestEnsureLayout:
    def test_ignores_everything_with_no_exemptions(self, repo: Repo) -> None:
        ignore = (repo.project.reportlab / ".gitignore").read_text()
        assert "*" in ignore.split("\n")
        # An exemption would leave `.reportlab/` untracked in every user's status.
        assert "!" not in ignore

    def test_writes_a_config_which_is_what_attaches_the_project(
        self, repo: Repo
    ) -> None:
        assert describe(repo.root).attached

    def test_creates_the_reports_directory(self, repo: Repo) -> None:
        assert repo.project.reports.is_dir()

    def test_does_not_overwrite_a_config_that_is_already_there(
        self, repo: Repo
    ) -> None:
        write_config(repo, '[rl]\nname = "mine"\n')
        ensure_layout(repo.project)
        assert describe(repo.root).name == "mine"

    def test_never_touches_the_users_own_ignore_file(self, repo: Repo) -> None:
        assert not (repo.root / ".gitignore").exists()
