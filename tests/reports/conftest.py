from __future__ import annotations

from pathlib import Path

import pytest

from tests.reports.repo import Repo


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo.create(tmp_path.resolve() / "repo")
