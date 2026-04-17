import os
import shutil
from pathlib import Path

from .conf import Config


def move_to_hd(path: Path):
    home = Path.home()
    hd_path = Config().hd.path
    hd_path.mkdir(exist_ok=True)

    path = path.resolve()
    target_path = hd_path / path.relative_to(home)

    shutil.move(str(path), str(target_path))
    os.symlink(str(target_path), str(path))
