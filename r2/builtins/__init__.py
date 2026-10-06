"""
Plugins shipped with r2.

Each subpackage has the layout of a user plugin (`plugin.toml` next to the
package) but imports as a regular module, `r2.builtins.<name>`. Which ones
load, and in which order, comes from `[r2] builtins` in config.toml;
`DEFAULT_BUILTINS` applies when that key is absent.
"""

from pathlib import Path

__all__ = ["DEFAULT_BUILTINS", "builtins_dir"]

#: Builtins loaded when the config does not list any, in tab order.
DEFAULT_BUILTINS: list[str] = []


def builtins_dir() -> Path:
    return Path(__file__).parent
