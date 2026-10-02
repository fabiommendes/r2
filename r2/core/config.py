"""User settings persisted as JSON.

Loading is lenient: a missing or broken file, or unknown keys, fall back to
the defaults, so a bad edit never keeps r2 from starting.
"""

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_DRAWER_WIDTH = 30


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def config_path() -> Path:
    """Return the path of the config file, honoring XDG_CONFIG_HOME."""
    return _config_home() / "r2" / "config.json"


def migrate_legacy_config(path: Path) -> None:
    """Copy the config of robin, r2's former name, to path, once.

    Nothing happens when path already exists or there is no robin config.
    The old file stays where it is.
    """
    legacy = _config_home() / "robin" / "config.json"
    if path.exists() or not legacy.is_file():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(legacy, path)
    except OSError:
        pass


@dataclass
class Config:
    drawer_widths: dict[str, int] = field(default_factory=dict)
    """Width of the drawer on the left of each view, by view id."""
    theme: str | None = None
    """Name of the Textual theme picked in the command palette."""

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        if path is None:
            path = config_path()
            migrate_legacy_config(path)
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
        """Write the config atomically, so a crash never leaves it half written."""
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2) + "\n")
        temporary.replace(path)

    def drawer_width(self, key: str) -> int:
        return self.drawer_widths.get(key, DEFAULT_DRAWER_WIDTH)
