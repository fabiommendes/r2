"""
Stand-in for the `task` command that the real `taskipy` package provides.

r2 runs project tasks via `uv run task <name>`, which normally resolves to
taskipy's console script reading `[tool.taskipy.tasks]` from pyproject.toml.
This example project defines the exact same table and reproduces just
enough of that behavior locally, so r2's integration tests don't need
network access or a real taskipy install to exercise r2's own code.
"""

import subprocess
import sys
import tomllib
from pathlib import Path


def main() -> None:
    name = sys.argv[1]
    data = tomllib.loads(Path("pyproject.toml").read_text())
    tasks = data.get("tool", {}).get("taskipy", {}).get("tasks", {})
    if name not in tasks:
        print(f"no such task: {name}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(subprocess.run(tasks[name], shell=True).returncode)
