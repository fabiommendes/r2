"""
Global configuration, read from `$R2_CONFIG_DIR/config.toml` (default:
`~/.config/r2/config.toml`).

Plugins keep their settings under `[plugins.<name>]`; see `r2.plugin.Plugin`.
"""

from __future__ import annotations

import contextlib
import os
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

CONFIG_DIR_ENV = "R2_CONFIG_DIR"
DEFAULT_CONFIG = """
[r2]
name = "{name}"

# Plugin settings go under [plugins.<name>], e.g.
#
# [plugins.sys]
# hd = "~/hd"
"""


class ConfigData(BaseModel):
    plugins: dict[str, dict[str, Any]] = Field(default_factory=dict)


def config_dir() -> Path:
    """
    Directory holding config.toml and the plugins/ folder.
    """
    if value := os.environ.get(CONFIG_DIR_ENV):
        return Path(value).expanduser()
    return Path.home() / ".config" / "r2"


def config_path() -> Path:
    return config_dir() / "config.toml"


def plugins_dir() -> Path:
    return config_dir() / "plugins"


class Config:
    """
    Main configuration class for the application. Implements a singleton
    pattern to ensure that only one instance of the configuration exists
    throughout the application.
    """

    _instance: Config | None = None
    _data: ConfigData

    @property
    def plugins(self) -> dict[str, dict[str, Any]]:
        return self._data.plugins

    def __new__(cls, *args: object, **kwargs: object) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str | None = None) -> None:
        if not hasattr(self, "_initialized"):
            path = config_path()
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(DEFAULT_CONFIG.format(name=name or infer_user_name()))
            with path.open("rb") as f:
                data = tomllib.load(f)

            self._data = ConfigData.model_validate(data)
            self._initialized = True

    @classmethod
    def reset(cls) -> None:
        """
        Drop the singleton so the next `Config()` re-reads the file.

        Useful for tests that point `R2_CONFIG_DIR` somewhere else.
        """
        cls._instance = None

    def __repr__(self) -> str:
        return f"Config(data={self._data!r})"

    def __str__(self) -> str:
        return str(self._data)


@contextlib.contextmanager
def set_config(data: ConfigData) -> Iterator[None]:
    """
    Temporarily set the configuration for the application.

    Not thread-safe, useful for testing.
    """
    cfg = Config()
    original_config = cfg._data
    cfg._data = data
    try:
        yield
    finally:
        cfg._data = original_config


def infer_user_name() -> str:
    """
    Infer the user's name from the environment or system settings.
    """
    import getpass

    name = os.environ.get("USER") or os.environ.get("USERNAME") or getpass.getuser()
    return name
