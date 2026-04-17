from __future__ import annotations

import contextlib
import tomllib
from pathlib import Path

from pydantic import BaseModel

CONFIG_PATH = Path.home() / ".config" / "r2" / "config.toml"
DEFAULT_CONFIG = """
[hd]
path = "~/hd"
"""


class ConfigHd(BaseModel):
    path: Path = Path("~/hd")


class ConfigData(BaseModel):
    hd: ConfigHd = ConfigHd()


class Config:
    """
    Main configuration class for the application. Implements a singleton
    pattern to ensure that only one instance of the configuration exists
    throughout the application.
    """

    _instance: Config | None = None
    _data: ConfigData

    @property
    def hd(self) -> ConfigHd:
        return self._data.hd

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            if not CONFIG_PATH.exists():
                CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with CONFIG_PATH.open("w") as f:
                    f.write(DEFAULT_CONFIG)
            with CONFIG_PATH.open() as f:
                data = tomllib.load(f)

            self._data = ConfigData.model_validate(data)
            self._initialized = True

    def __repr__(self):
        return f"Config(data={self._data!r})"

    def __str__(self):
        return str(self._data)


@contextlib.contextmanager
def set_config(data: ConfigData):
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
