"""User settings persisted as JSON.

Loading is lenient: a missing or broken file, or unknown keys, fall back to
the defaults, so a bad edit never keeps robin from starting.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_DRAWER_WIDTH = 30


def config_path() -> Path:
    """Return the path of the config file, honoring XDG_CONFIG_HOME."""
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "robin" / "config.json"


@dataclass
class Config:
    drawer_widths: dict[str, int] = field(default_factory=dict)
    """Width of the drawer on the left of each view, by view id."""

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        try:
            data = json.loads((path or config_path()).read_text())
            widths = data.get("drawer_widths", {})
            return cls(drawer_widths={str(k): int(v) for k, v in widths.items()})
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
