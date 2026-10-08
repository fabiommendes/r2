"""
Tests for the safe file writes in r2.core.files.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path

import pytest

from r2.core.files import atomic_write, create, update


def test_atomic_write_replaces_the_text(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("old")
    atomic_write(path, "new")
    assert path.read_text() == "new"


def test_atomic_write_leaves_no_temporary_file(tmp_path: Path) -> None:
    atomic_write(tmp_path / "a.md", "text")
    assert [p.name for p in tmp_path.iterdir()] == ["a.md"]


def test_atomic_write_keeps_the_permissions(tmp_path: Path) -> None:
    path = tmp_path / "a.sh"
    path.write_text("old")
    path.chmod(0o751)
    atomic_write(path, "new")
    assert path.stat().st_mode & 0o777 == 0o751


def test_atomic_write_follows_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("old")
    link = tmp_path / "link.md"
    link.symlink_to(target)

    atomic_write(link, "new")

    assert link.is_symlink()
    assert target.read_text() == "new"


def test_update_reads_a_missing_file_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    assert update(path, lambda text: text + "line\n") == "line\n"
    assert path.read_text() == "line\n"


def test_update_skips_the_write_when_nothing_changes(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("same")
    before = path.stat().st_ino
    update(path, lambda text: text)
    assert path.stat().st_ino == before


def _append(path: str, line: str) -> None:
    update(Path(path), lambda text: text + line + "\n")


def test_concurrent_updates_lose_no_change(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("")
    lines = [f"line {n}" for n in range(40)]

    context = multiprocessing.get_context("fork")
    with context.Pool(8) as pool:
        pool.starmap(_append, [(str(path), line) for line in lines])

    assert sorted(path.read_text().splitlines()) == sorted(lines)


def test_create_writes_at_the_picked_path(tmp_path: Path) -> None:
    folder = tmp_path / "issues"
    path = create(folder, lambda folder: folder / "a.md", "text")
    assert path == folder / "a.md"
    assert path.read_text() == "text"


def test_create_never_overwrites(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("old")
    with pytest.raises(FileExistsError):
        create(tmp_path, lambda folder: folder / "a.md", "new")
    assert (tmp_path / "a.md").read_text() == "old"
