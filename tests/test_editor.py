from pathlib import Path

import pytest

from r2.editor import editor_command
from r2.links import Link


def test_editor_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    link = Link(Path("/a.py"), 10, 12)
    monkeypatch.setenv("R2_EDITOR", "nvim -u NONE")
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.setenv("VISUAL", "code")
    assert editor_command(link) == ["nvim", "-u", "NONE", "+10", "/a.py"]
    monkeypatch.delenv("R2_EDITOR")
    assert editor_command(link) == ["nano", "+10", "/a.py"]
    monkeypatch.delenv("EDITOR")
    assert editor_command(link) == ["code", "+10", "/a.py"]
    monkeypatch.delenv("VISUAL")
    assert editor_command(Link(Path("/a.py"))) == ["micro", "/a.py"]


def test_ide_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    from r2.editor import ide_command

    monkeypatch.setenv("R2_IDE", "zed --new")
    monkeypatch.setenv("VISUAL", "code")
    assert ide_command(Path("/p")) == ["zed", "--new", "/p"]
    monkeypatch.delenv("R2_IDE")
    assert ide_command(Path("/p")) == ["code", "/p"]
    monkeypatch.delenv("VISUAL")
    assert ide_command(Path("/p")) == ["code", "/p"]
