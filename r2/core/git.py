"""Branch and worktree state of a project, from `git status`."""

import asyncio
import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Worktree(Enum):
    DIRTY = "dirty"
    """Some change is not staged, or some file is untracked."""
    STAGED = "staged"
    """Every change is staged."""
    CLEAN = "clean"
    """Nothing to commit."""


@dataclass(frozen=True)
class GitStatus:
    branch: str
    worktree: Worktree


def parse_status(output: str) -> GitStatus:
    """Parse `git status --porcelain=v1 --branch`."""
    header, *entries = output.splitlines() or ["## "]
    branch = header.removeprefix("## ")
    if branch.startswith("No commits yet on "):
        branch = branch.removeprefix("No commits yet on ")
    elif branch.startswith("HEAD (no branch)"):
        branch = "detached"
    else:
        branch = branch.split("...")[0]

    entries = [entry for entry in entries if entry]
    if any(entry.startswith("??") or entry[1] != " " for entry in entries):
        worktree = Worktree.DIRTY
    elif entries:
        worktree = Worktree.STAGED
    else:
        worktree = Worktree.CLEAN
    return GitStatus(branch, worktree)


async def status(root: Path) -> GitStatus | None:
    """Return the status of the repository at root, or None if it is not one.

    --no-optional-locks keeps git from writing the index, so polling never
    makes a concurrent git command fail on index.lock.
    """
    process = await asyncio.create_subprocess_exec(
        "git",
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "--branch",
        cwd=root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    output, _ = await process.communicate()
    if process.returncode != 0:
        return None
    return parse_status(output.decode(errors="replace"))


def user_name(root: Path) -> str:
    """The git user.name of the project at root, or the login name."""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=2,
        )
        name = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        name = ""
    return name or os.environ.get("USER", "")
