"""
Public API for global plugin authors.

```python
# ~/.config/r2/plugins/sys/__init__.py
from pathlib import Path
from pydantic import BaseModel
from r2.plugin import Plugin

class SysConfig(BaseModel):
    hd: Path = Path("~/hd")

plugin = Plugin("sys", config=SysConfig)

@plugin.command()
def hd(path: Path) -> None:
    target = plugin.settings.hd
    ...
```

Command metadata (help, destructive, hidden, interactive) lives in the
sibling `plugin.toml`, which r2 reads without importing this module.

Print through `plugin.console` and `plugin.err`, and read `plugin.mode`
for the verbosity and --json: agent mode swaps those consoles for plain
ones, so output stays uniform across r2.

Panes for the TUI are registered the same way, with `@plugin.pane()` on a
`r2.tui.PluginPane` subclass, and declared under `[panes.<name>]`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from rich.console import Console

    from r2.core.mode import Mode

__all__ = ["Plugin"]

type Command = Callable[..., Any]

#: Kept untyped so this module never imports Textual.
type PaneClass = type


class Plugin[C: BaseModel = BaseModel]:
    """
    Registry of a plugin's command functions and its settings model.
    """

    def __init__(self, name: str, config: type[C] | None = None):
        self.name = name
        self.config_model: type[C] | None = config
        self.commands: dict[str, Command] = {}
        self.panes: dict[str, PaneClass] = {}

    def command(self, name: str | None = None) -> Callable[[Command], Command]:
        """
        Decorator that register a function as the implementation of a command.

        The command name defaults to the function name, with underscores
        replaced by dashes, and must match an entry in `plugin.toml`.
        """

        def decorator(fn: Command) -> Command:
            self.commands[name or fn.__name__.replace("_", "-")] = fn
            return fn

        return decorator

    def pane[T: PaneClass](self, name: str | None = None) -> Callable[[T], T]:
        """
        Register a `r2.tui.PluginPane` subclass as one of the plugin's panes.

        The pane name defaults to the class name in kebab case, without a
        trailing "Pane" (`AliasListPane` -> "alias-list"), and must match an
        entry in `plugin.toml`.
        """

        def decorator(cls: T) -> T:
            self.panes[name or pane_name(cls)] = cls
            return cls

        return decorator

    @property
    def console(self) -> Console:
        """
        Where command output goes. Print through it, not through a Console
        of your own, so agent mode can strip colors and styles.
        """
        from r2.core import console

        return console.stdout

    @property
    def err(self) -> Console:
        """Where warnings and errors go: stderr, styled like `console`."""
        from r2.core import console

        return console.stderr

    @property
    def mode(self) -> Mode:
        """The global mode: agent, verbosity, json and yes."""
        from r2.core.mode import mode

        return mode

    @property
    def settings(self) -> C:
        """
        Validated settings: `[plugins.<name>]` from the global config, with
        `[config.<name>]` from the project manifest layered on top.
        """
        from r2.cli.registry import registry

        if self.config_model is None:
            raise RuntimeError(f"Plugin {self.name!r} declares no config model")
        return self.config_model.model_validate(registry.settings_for(self.name))


def pane_name(cls: type) -> str:
    base = cls.__name__.removesuffix("Pane") or cls.__name__
    return re.sub(r"(?<!^)(?=[A-Z])", "-", base).lower()
