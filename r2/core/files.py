"""
File helpers: safe writes and moves.

Every write r2 does to a project file goes through `atomic_write`, and every
read-modify-write cycle through `update`, so concurrent r2 processes never
leave a half written file or overwrite each other's changes. Locks are
advisory `flock` locks on the folder that holds the file, so no lock files
are left behind. Linux and macOS only.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = ["atomic_write", "create", "locked", "move_to_hd", "update"]


def atomic_write(path: Path, text: str) -> None:
    """
    Replace the contents of path with text in one step.

    The text goes to a temporary file in the same folder, which then
    replaces the target, keeping its permissions. A symlink is followed, so
    it keeps pointing to the same file.
    """
    target = path.resolve()
    try:
        mode = target.stat().st_mode & 0o7777
    except FileNotFoundError:
        mode = 0o666 & ~_umask()
    fd, temporary = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


@contextmanager
def locked(folder: Path) -> Iterator[None]:
    """
    Hold an exclusive lock on folder while the block runs.

    Only other r2 processes respect it: the lock is advisory.
    """
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def update(path: Path, change: Callable[[str], str]) -> str:
    """
    Apply change to the text of path and write the result, under a lock.

    The file is read after the lock is taken, so change always sees the
    latest text; a missing file reads as empty. Return the new text.
    """
    target = path.resolve()
    with locked(target.parent):
        try:
            text = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        new = change(text)
        if new != text:
            atomic_write(target, new)
    return new


def create(folder: Path, pick: Callable[[Path], Path], text: str) -> Path:
    """
    Write text to a new file in folder, at the path pick chooses.

    pick runs under the folder lock, so two processes never choose the same
    name. Raise FileExistsError instead of overwriting a file.
    """
    folder.mkdir(parents=True, exist_ok=True)
    with locked(folder):
        path = pick(folder)
        if path.exists():
            raise FileExistsError(path)
        atomic_write(path, text)
    return path


def _umask() -> int:
    # os.umask can only be read by setting it, which races with other
    # threads creating files; Linux exposes it in /proc instead.
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("Umask:"):
                return int(line.split()[1], 8)
    except OSError:
        pass
    return 0o022


def move_to_hd(path: Path, hd_path: Path) -> None:
    """
    Move `path` (which must live under $HOME) to the same relative location
    under `hd_path`, then symlink the old location to the new one.
    """
    home = Path.home()
    hd_path.mkdir(parents=True, exist_ok=True)

    path = path.resolve()
    target_path = hd_path / path.relative_to(home)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(str(path), str(target_path))
    os.symlink(str(target_path), str(path))
