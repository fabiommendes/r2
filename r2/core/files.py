import os
import shutil
from pathlib import Path


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
