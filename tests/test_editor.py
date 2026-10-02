from pathlib import Path

import pytest

from robin.editor import editor_command
from robin.links import Link


def test_uses_visual_then_editor_then_micro(monkeypatch: pytest.MonkeyPatch) -> None:
    link = Link(Path("/a.py"), 10, 12)
    monkeypatch.setenv("VISUAL", "nvim -u NONE")
    monkeypatch.setenv("EDITOR", "nano")
    assert editor_command(link) == ["nvim", "-u", "NONE", "+10", "/a.py"]
    monkeypatch.delenv("VISUAL")
    assert editor_command(link) == ["nano", "+10", "/a.py"]
    monkeypatch.delenv("EDITOR")
    assert editor_command(Link(Path("/a.py"))) == ["micro", "/a.py"]
