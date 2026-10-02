import asyncio
import subprocess
from pathlib import Path

import pytest

from robin.git import GitStatus, Worktree, parse_status, status


def test_parse_branch_names() -> None:
    assert parse_status("## main...origin/main [ahead 1]\n").branch == "main"
    assert parse_status("## feat/x\n").branch == "feat/x"
    assert parse_status("## No commits yet on main\n").branch == "main"
    assert parse_status("## HEAD (no branch)\n").branch == "detached"


def test_parse_worktree_state() -> None:
    assert parse_status("## main\n").worktree is Worktree.CLEAN
    assert parse_status("## main\nM  a.py\nA  b.py\n").worktree is Worktree.STAGED
    assert parse_status("## main\nMM a.py\n").worktree is Worktree.DIRTY
    assert parse_status("## main\n M a.py\n").worktree is Worktree.DIRTY
    assert parse_status("## main\nA  a.py\n?? new.py\n").worktree is Worktree.DIRTY


def test_status_of_a_real_repository(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "trunk")
    (tmp_path / "a.txt").write_text("a")
    assert asyncio.run(status(tmp_path)) == GitStatus("trunk", Worktree.DIRTY)
    git("add", "a.txt")
    assert asyncio.run(status(tmp_path)) == GitStatus("trunk", Worktree.STAGED)


def test_status_outside_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "plain").mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    assert asyncio.run(status(tmp_path / "plain")) is None
