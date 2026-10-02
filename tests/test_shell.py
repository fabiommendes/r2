import asyncio
from pathlib import Path

import pytest

from robin import shell


def test_change_directory(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assert shell.change_directory("cd src", tmp_path, tmp_path) == tmp_path / "src"
    assert shell.change_directory("cd ..", tmp_path / "src", tmp_path) == tmp_path
    assert shell.change_directory("cd", tmp_path / "src", tmp_path) == tmp_path
    with pytest.raises(NotADirectoryError):
        shell.change_directory("cd missing", tmp_path, tmp_path)


def test_start_merges_output_and_sets_env(tmp_path: Path) -> None:
    async def run() -> bytes:
        process = await shell.start("echo $COLUMNS; echo err >&2", tmp_path, 77)
        out, _ = await process.communicate()
        return out

    assert asyncio.run(run()).split() == [b"77", b"err"]
