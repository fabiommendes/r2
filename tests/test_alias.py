from pathlib import Path

import pytest
import typer

from r2.core import alias


@pytest.fixture
def alias_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".bash_aliases"
    path.write_text("# git\nalias gs='git status'\n")
    monkeypatch.setattr(alias, "BASH_ALIAS_PATH", path)
    return path


def test_adds_alias_to_an_existing_section(alias_file: Path) -> None:
    alias.create_alias(py=True, js=False, package="", alias="ruff", section="git")
    assert alias_file.read_text() == (
        "# git\nalias ruff='uvx ruff'\nalias gs='git status'\n"
    )


def test_creates_missing_section(alias_file: Path) -> None:
    alias.create_alias(py=False, js=True, package="pkg", alias="tool", section="js")
    assert alias_file.read_text().endswith(
        "\n# js\nalias tool='npx --yes --package pkg tool'\n"
    )


def test_duplicate_alias_is_an_error(alias_file: Path) -> None:
    with pytest.raises(typer.Exit):
        alias.create_alias(py=True, js=False, package="", alias="gs", section="")


def test_parse_sections(alias_file: Path) -> None:
    assert alias.parse_sections() == {"git": [("gs", "'git status'")]}
