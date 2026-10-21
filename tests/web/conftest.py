from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.reports.repo import Repo


@pytest.fixture(autouse=True)
def machine_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep the registry, the daemon files and r2's config inside tmp_path."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("R2_CONFIG_DIR", str(tmp_path / "r2-config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo.create(tmp_path.resolve() / "repo")


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[[str], Repo]:
    """Another attached repository, by directory name."""

    def make(name: str) -> Repo:
        return Repo.create(tmp_path.resolve() / "repos" / name)

    return make
