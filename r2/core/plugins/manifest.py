"""
Schemas for the two plugin manifests.

Global plugin (`$R2_CONFIG_DIR/plugins/<name>/plugin.toml`):

```toml
[plugin]
name = "sys"
help = "Machine-specific helpers."

[commands.hd]
help = "Move a path to the hard drive."
destructive = true
hidden = true
```

The plugin folder is a Python package; its `__init__.py` exposes a
`r2.plugin.Plugin` instance called `plugin` with one function per command.
Only the manifest is read at startup; the package is imported when one of
its commands runs.

Panes for the TUI are declared the same way:

```toml
[panes.aliases]
title = "Aliases"
help = "Browse and edit shell aliases."
```

Project manifest (`r2.toml` at the project root, or `[tool.r2]` in
`pyproject.toml`):

```toml
[commands.db-reset]
run = "uv run python scripts/db.py reset"
help = "Drop and recreate the dev database."
destructive = true

[config.sys]
hd = "~/hd2"
```

Project commands are shell commands, run in the project's own environment.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "CommandSpec",
    "PaneSpec",
    "PluginInfo",
    "PluginManifest",
    "ProjectCommand",
    "ProjectManifest",
]


NAME = re.compile(r"[a-z][a-z0-9_-]*")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommandSpec(Strict):
    """
    Agent-facing metadata shared by global and project commands.
    """

    help: str = ""
    #: In agent mode, the command refuses to run without --yes.
    destructive: bool = False
    #: Left out of `r2 help` listings (still callable).
    hidden: bool = False
    #: The command reads from stdin; otherwise stdin is closed in agent mode.
    interactive: bool = False


class PaneSpec(Strict):
    #: Tab label. Defaults to the pane name.
    title: str = ""
    help: str = ""


class PluginInfo(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    help: str = ""


class PluginManifest(Strict):
    plugin: PluginInfo
    commands: dict[str, CommandSpec] = Field(default_factory=dict)
    panes: dict[str, PaneSpec] = Field(default_factory=dict)

    @field_validator("panes")
    @classmethod
    def check_pane_names(cls, panes: dict[str, PaneSpec]) -> dict[str, PaneSpec]:
        # Pane names end up in Textual widget ids.
        for name in panes:
            if not NAME.fullmatch(name):
                raise ValueError(f"invalid pane name {name!r}: use [a-z][a-z0-9_-]*")
        return panes


class ProjectCommand(CommandSpec):
    run: str
    #: Whether extra command-line arguments are appended to `run`.
    args: Literal["none", "passthrough"] = "passthrough"
    #: Working directory, relative to the project root.
    cwd: str = "."
    env: dict[str, str] = Field(default_factory=dict)
    timeout: float | None = None
    #: "summary" is reduced in agent mode; "passthrough" is never reduced.
    output: Literal["summary", "passthrough"] = "summary"


class ProjectManifest(Strict):
    commands: dict[str, ProjectCommand] = Field(default_factory=dict)
    #: Per-plugin settings, overriding `[plugins.<name>]` in the global config.
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)
