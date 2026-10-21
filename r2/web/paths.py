"""Where the viewer keeps its machine-wide files."""

from __future__ import annotations

import os
from pathlib import Path

from r2.core.conf import config_dir

__all__ = ["daemon_file", "lock_file", "registry_file", "settings_file", "state_dir"]


def state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / "r2" / "web"


def registry_file() -> Path:
    """The attached projects. Owned by r2, never edited by hand."""
    return state_dir() / "projects.json"


def daemon_file() -> Path:
    """Pid, port and token of the running daemon."""
    return state_dir() / "daemon.json"


def lock_file() -> Path:
    return state_dir() / "daemon.lock"


def settings_file() -> Path:
    """r2's own config file; the viewer reads its `[web]` table."""
    return config_dir() / "config.toml"
