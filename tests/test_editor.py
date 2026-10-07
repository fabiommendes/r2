from pathlib import Path

import pytest

from r2.core.conf import Config
from r2.core.editor import editor_command
from r2.core.links import Link


def test_editor_precedence(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (config / "config.toml").write_text('[r2]\neditor = "vim"\n')
    link = Link(Path("/a.py"), 10, 12)
    monkeypatch.setenv("R2_EDITOR", "nvim -u NONE")
    monkeypatch.setenv("EDITOR", "nano")
    monkeypatch.setenv("VISUAL", "code")
    assert editor_command(link) == ["nvim", "-u", "NONE", "+10", "/a.py"]
    monkeypatch.delenv("R2_EDITOR")
    assert editor_command(link) == ["vim", "+10", "/a.py"]
    (config / "config.toml").write_text("")
    Config.reset()
    assert editor_command(link) == ["nano", "+10", "/a.py"]
    monkeypatch.delenv("EDITOR")
    assert editor_command(link) == ["code", "--goto", "/a.py:10"]
    monkeypatch.setenv("VISUAL", "/usr/bin/codium -w")
    assert editor_command(link) == ["/usr/bin/codium", "-w", "--goto", "/a.py:10"]
    monkeypatch.delenv("VISUAL")
    assert editor_command(Link(Path("/a.py"))) == ["micro", "/a.py"]


def test_ide_precedence(config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from r2.core.editor import ide_command

    (config / "config.toml").write_text('[r2]\nide = "subl"\n')
    monkeypatch.setenv("R2_IDE", "zed --new")
    monkeypatch.setenv("VISUAL", "code")
    assert ide_command(Path("/p")) == ["zed", "--new", "/p"]
    monkeypatch.delenv("R2_IDE")
    assert ide_command(Path("/p")) == ["subl", "/p"]
    (config / "config.toml").write_text("")
    Config.reset()
    assert ide_command(Path("/p")) == ["code", "/p"]
    monkeypatch.delenv("VISUAL")
    assert ide_command(Path("/p")) == ["code", "/p"]
