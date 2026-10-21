from __future__ import annotations

from pathlib import Path

import pytest

from r2.web.settings import DEFAULT_DEPTH, Settings, read_settings


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    return tmp_path / "settings.toml"


def settings_from(config_file: Path, text: str) -> Settings:
    config_file.write_text(text)
    return read_settings(config_file)


class TestReadSettings:
    def test_is_off_by_default(self, config_file: Path) -> None:
        assert read_settings(config_file) == Settings()
        assert Settings().roots == []
        assert Settings().depth == DEFAULT_DEPTH

    def test_reads_roots_and_depth(self, config_file: Path) -> None:
        value = settings_from(
            config_file, '[web.discover]\nroots = ["/a", "/b"]\ndepth = 3\n'
        )
        assert value.roots == [Path("/a"), Path("/b")]
        assert value.depth == 3
        assert value.error is None

    def test_reads_the_table_inside_the_shared_config_file(
        self, config_file: Path
    ) -> None:
        value = settings_from(
            config_file,
            'editor = "vim"\n\n[tui]\ntheme = "dark"\n\n'
            '[web.discover]\nroots = ["/a"]\n',
        )
        assert value.roots == [Path("/a")]
        assert value.error is None

    def test_without_an_explicit_file_reads_r2s_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = tmp_path / "cfg"
        config.mkdir()
        (config / "config.toml").write_text('[web.discover]\nroots = ["/a"]\n')
        monkeypatch.setenv("R2_CONFIG_DIR", str(config))
        assert read_settings().roots == [Path("/a")]

    def test_the_old_top_level_discover_table_is_not_read(
        self, config_file: Path
    ) -> None:
        value = settings_from(config_file, '[discover]\nroots = ["/a"]\n')
        assert value.roots == []

    def test_expands_a_leading_tilde(
        self, config_file: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        value = settings_from(config_file, '[web.discover]\nroots = ["~/git", "~"]\n')
        assert value.roots == [home / "git", home]

    def test_caps_the_depth(self, config_file: Path) -> None:
        value = settings_from(
            config_file, '[web.discover]\nroots = ["/a"]\ndepth = 9999\n'
        )
        assert value.depth == 24

    def test_a_depth_of_zero_is_allowed(self, config_file: Path) -> None:
        assert settings_from(config_file, "[web.discover]\ndepth = 0\n").depth == 0

    @pytest.mark.parametrize("depth", ['"deep"', "-1", "true", "2.5"])
    def test_reports_a_depth_that_is_not_a_whole_number(
        self, config_file: Path, depth: str
    ) -> None:
        value = settings_from(config_file, f"[web.discover]\ndepth = {depth}\n")
        assert value.error is not None
        assert "depth" in value.error
        assert value.depth == DEFAULT_DEPTH

    def test_drops_entries_that_are_not_strings(self, config_file: Path) -> None:
        value = settings_from(
            config_file, '[web.discover]\nroots = ["/a", 7, "", "  "]\n'
        )
        assert value.roots == [Path("/a")]

    def test_reports_invalid_toml_and_keeps_the_defaults(
        self, config_file: Path
    ) -> None:
        value = settings_from(config_file, "[web.discover\n")
        assert value.error is not None
        assert "not valid TOML" in value.error
        assert value.roots == []
        assert value.depth == DEFAULT_DEPTH

    def test_reports_a_roots_value_that_is_not_a_list(self, config_file: Path) -> None:
        value = settings_from(config_file, '[web.discover]\nroots = "~/git"\n')
        assert value.error is not None
        assert "must be a list" in value.error
        assert value.roots == []

    def test_ignores_unknown_sections_and_keys(self, config_file: Path) -> None:
        value = settings_from(
            config_file,
            '[web.discover]\nroots = ["/a"]\nfuture = 1\n\n[future]\nx = 1\n',
        )
        assert value.error is None
        assert value.roots == [Path("/a")]

    def test_a_web_table_that_is_not_a_table_is_ignored(
        self, config_file: Path
    ) -> None:
        value = settings_from(config_file, 'web = "nope"\n')
        assert value == Settings()
