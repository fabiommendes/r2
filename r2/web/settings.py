"""
Machine-wide settings of the viewer, in the `[web]` table of r2's
`config.toml`:

    [web.discover]
    roots = ["~/git", "~/work"]
    depth = 6

Read leniently: a file that cannot be parsed leaves the defaults in place
and `error` says why.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from r2.web.paths import settings_file

__all__ = ["DEFAULT_DEPTH", "Settings", "read_settings"]

DEFAULT_DEPTH = 6
MAX_DEPTH = 24


@dataclass
class Settings:
    #: Absolute paths. Empty means discovery is off, which is the default.
    roots: list[Path] = field(default_factory=list)
    #: How deep to look below each root.
    depth: int = DEFAULT_DEPTH
    #: Why the file was ignored.
    error: str | None = None


def read_settings(path: Path | None = None) -> Settings:
    settings = Settings()
    try:
        text = (path or settings_file()).read_text(encoding="utf-8")
    except OSError:
        return settings
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        settings.error = f"config.toml is not valid TOML: {error}"
        return settings

    web = parsed.get("web")
    discover = web.get("discover") if isinstance(web, dict) else None
    if not isinstance(discover, dict):
        return settings

    roots = discover.get("roots")
    if isinstance(roots, list):
        settings.roots = [
            Path(root.strip()).expanduser().resolve()
            for root in roots
            if isinstance(root, str) and root.strip()
        ]
    elif roots is not None:
        settings.error = "config.toml: [web.discover] roots must be a list of paths"

    depth = discover.get("depth")
    if isinstance(depth, int) and not isinstance(depth, bool) and depth >= 0:
        settings.depth = min(depth, MAX_DEPTH)
    elif depth is not None:
        settings.error = "config.toml: [web.discover] depth must be a whole number"
    return settings
