"""
Tests for the bundled `sys` plugin (plugins/sys), installed into a private
config dir exactly as a user would do it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import build_app
from r2.core.conf import Config
from r2.core.plugins import loader
from tests.support import REPO_ROOT

runner = CliRunner()


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    config = home / ".config" / "r2"
    (config / "plugins").mkdir(parents=True)
    (config / "plugins" / "sys").symlink_to(REPO_ROOT / "plugins" / "sys")
    (config / "config.toml").write_text(f'[plugins.sys]\nhd = "{home / "disk"}"\n')

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("R2_CONFIG_DIR", str(config))
    monkeypatch.delenv("R2_AGENT", raising=False)
    monkeypatch.chdir(home)
    Config.reset()
    loader.reset()
    return home


def run(*args: str):
    return runner.invoke(build_app(), list(args))


def test_sys_plugin_is_discovered_and_healthy(home: Path) -> None:
    out = run("plugins", "list").output
    assert "global   sys" in out and "hd, alias" in out
    assert run("plugins", "doctor").exit_code == 0


def test_hd_moves_path_and_leaves_symlink(home: Path) -> None:
    big = home / "videos" / "big.bin"
    big.parent.mkdir()
    big.write_bytes(b"x" * 10)

    result = run("hd", str(big))
    assert result.exit_code == 0, result.output

    moved = home / "disk" / "videos" / "big.bin"
    assert moved.is_file() and moved.read_bytes() == b"x" * 10
    assert big.is_symlink() and big.resolve() == moved


def test_hd_is_destructive_in_agent_mode(home: Path) -> None:
    (home / "f").write_text("")
    assert run("--agent", "hd", str(home / "f")).exit_code == 2
    assert run("--agent", "--yes", "hd", str(home / "f")).exit_code == 0


def test_alias_adds_to_section_and_rejects_duplicates(home: Path) -> None:
    aliases = home / ".bash_aliases"
    aliases.write_text("# Tools\nalias gs='git status'\n")

    assert run("alias", "--py", "ruff", "--section", "Tools").exit_code == 0
    assert run("alias", "--js", "--from", "typescript", "tsc").exit_code == 0

    text = aliases.read_text()
    assert "# Tools\nalias ruff='uvx ruff'\nalias gs='git status'\n" in text
    assert "# Other\nalias tsc='npx --yes --package typescript tsc'" in text

    result = run("alias", "--py", "ruff")
    assert result.exit_code == 1 and "already exists" in result.output

    out = run("alias", "--list").output
    assert "Tools" in out and "ruff" in out and "Other" in out
