import os
import subprocess
from collections.abc import Callable
from pathlib import Path

ExampleProjectFactory = Callable[[str], Path]

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_ROOT = REPO_ROOT / "tests" / "examples" / "pyproject"


def run_r2(
    *args: str, cwd: Path, timeout: float = 120
) -> subprocess.CompletedProcess[str]:
    """
    Run the real `r2` CLI as a subprocess, from `cwd`.

    r2's project tasks dispatch through `os.execvpe`, which replaces the
    calling process outright, so they have to be exercised out of process
    rather than by calling the Python API in-thread. `uv run --project` is
    used instead of relying on a bare `r2` on PATH, so the suite exercises
    this checkout of r2 regardless of what else is installed.
    """
    cmd = ["uv", "run", "--project", str(REPO_ROOT), "r2", *args]
    print(f"$ r2 {' '.join(args)} (cwd={cwd})")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        print(f"r2 failed with exit code {result.returncode}")
        print("stderr:")
        print(result.stderr)
    return result
