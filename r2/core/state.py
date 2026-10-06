"""UI state that the TUI saves by itself: drawer widths and theme.

This is not configuration: nobody is meant to edit it, so it lives in
`$XDG_STATE_HOME/r2/tui.json`, apart from the hand-edited
`~/.config/r2/config.toml` (see `r2.core.conf`).

Loading is lenient: a missing or broken file, or unknown keys, fall back to
the defaults, so a bad file never keeps r2 from starting.
"""

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_DRAWER_WIDTH = 30


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _state_home() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")


def state_path() -> Path:
    """Return the path of the state file, honoring XDG_STATE_HOME."""
    return _state_home() / "r2" / "tui.json"


def legacy_paths() -> list[Path]:
    """Older homes of this file, newest first: r2's config dir, then robin's."""
    return [
        _config_home() / "r2" / "config.json",
        _config_home() / "robin" / "config.json",
    ]


def migrate_legacy_state(path: Path) -> None:
    """Copy the newest legacy file to path, once.

    Nothing happens when path already exists or there is no legacy file. The
    old file stays where it is.
    """
    if path.exists():
        return
    legacy = next((p for p in legacy_paths() if p.is_file()), None)
    if legacy is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(legacy, path)
    except OSError:
        pass


@dataclass
class UIState:
    drawer_widths: dict[str, int] = field(default_factory=dict)
    """Width of the drawer on the left of each tab, by drawer key."""
    theme: str | None = None
    """Name of the Textual theme picked in the command palette."""

    @classmethod
    def load(cls, path: Path | None = None) -> "UIState":
        if path is None:
            path = state_path()
            migrate_legacy_state(path)
        try:
            data = json.loads(path.read_text())
            widths = data.get("drawer_widths", {})
            theme = data.get("theme")
            return cls(
                drawer_widths={str(k): int(v) for k, v in widths.items()},
                theme=theme if isinstance(theme, str) else None,
            )
        except (OSError, ValueError, AttributeError, TypeError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        """Write the file atomically, so a crash never leaves it half written."""
        path = path or state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2) + "\n")
        temporary.replace(path)

    def drawer_width(self, key: str) -> int:
        return self.drawer_widths.get(key, DEFAULT_DRAWER_WIDTH)
