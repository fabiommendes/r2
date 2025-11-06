import os
import shutil
from pathlib import Path


def move_to_hd(path: Path):
    home = Path.home()
    hd_path = home / "hd"
    hd_path.mkdir(exist_ok=True)

    path = path.resolve()
    target_path = hd_path / path.relative_to(home)

    shutil.move(str(path), str(target_path))
    os.symlink(str(target_path), str(path))
