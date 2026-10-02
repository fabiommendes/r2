import os
import subprocess
from pathlib import Path


def edit(file: Path):
    editor = os.environ.get("EDITOR", "nano")

    subprocess.run([editor, str(file)])
