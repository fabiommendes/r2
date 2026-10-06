"""
Find plugins without importing any plugin code.

Two tiers:

- Global: the builtins selected in the config (`r2.builtins`), then every
  folder under `plugins_dir()` holding a `plugin.toml`. A user plugin with
  the name of a builtin replaces it.
- Project: the first `r2.toml` found walking up from the start directory;
  failing that, a `[tool.r2]` table in `pyproject.toml`.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from r2.core.conf import plugins_dir
from r2.core.plugins.manifest import (
    CommandSpec,
    PaneSpec,
    PluginManifest,
    ProjectCommand,
    ProjectManifest,
)

__all__ = [
    "GlobalPlugin",
    "Problem",
    "ProjectPlugin",
    "discover_global",
    "discover_project",
    "find_project_manifest",
]

PROJECT_MANIFEST = "r2.toml"
PLUGIN_MANIFEST = "plugin.toml"


@dataclass(frozen=True)
class Problem:
    """
    Something that stopped a plugin from loading. Reported by `r2 plugins doctor`.
    """

    source: Path
    message: str

    def __str__(self) -> str:
        return f"{self.source}: {self.message}"


@dataclass(frozen=True)
class GlobalPlugin:
    name: str
    help: str
    root: Path
    commands: dict[str, CommandSpec] = field(default_factory=dict)
    panes: dict[str, PaneSpec] = field(default_factory=dict)
    #: Shipped with r2, importable as `r2.builtins.<name>`.
    builtin: bool = False

    @property
    def manifest(self) -> Path:
        return self.root / PLUGIN_MANIFEST


@dataclass(frozen=True)
class ProjectPlugin:
    root: Path
    source: Path
    commands: dict[str, ProjectCommand] = field(default_factory=dict)
    config: dict[str, dict[str, Any]] = field(default_factory=dict)


def discover_global(
    directory: Path | None = None,
    builtins: list[str] | None = None,
) -> tuple[list[GlobalPlugin], list[Problem]]:
    """
    The global plugins to load, in order: the selected builtins, then the
    remaining user plugins sorted by folder name.

    `builtins` defaults to `[r2] builtins` from the config, or
    `DEFAULT_BUILTINS` when the config has no such key.
    """
    from r2.builtins import DEFAULT_BUILTINS, builtins_dir

    if builtins is None:
        from r2.core.conf import Config

        builtins = Config().builtins
        if builtins is None:
            builtins = DEFAULT_BUILTINS

    shipped, problems = scan(builtins_dir(), builtin=True)
    user, user_problems = scan(directory or plugins_dir())
    problems += user_problems
    available = {p.name: p for p in shipped}
    mine = {p.name: p for p in user}

    plugins: list[GlobalPlugin] = []
    for name in dict.fromkeys(builtins):
        if name in mine:
            plugins.append(mine.pop(name))
        elif name in available:
            plugins.append(available[name])
        else:
            msg = f"unknown builtin plugin {name!r} in [r2] builtins"
            problems.append(Problem(config_file(), msg))
    plugins += mine.values()
    return plugins, problems


def available_builtins() -> list[GlobalPlugin]:
    """
    Every plugin shipped with r2, selected or not.
    """
    from r2.builtins import builtins_dir

    return scan(builtins_dir(), builtin=True)[0]


def config_file() -> Path:
    from r2.core.conf import config_path

    return config_path()


def scan(
    directory: Path, builtin: bool = False
) -> tuple[list[GlobalPlugin], list[Problem]]:
    """
    Read every `<dir>/*/plugin.toml`, sorted by folder name.
    """
    plugins: list[GlobalPlugin] = []
    problems: list[Problem] = []

    if not directory.is_dir():
        return plugins, problems

    for root in sorted(p for p in directory.iterdir() if p.is_dir()):
        path = root / PLUGIN_MANIFEST
        if not path.is_file():
            continue
        try:
            manifest = PluginManifest.model_validate(read_toml(path))
        except (tomllib.TOMLDecodeError, ValidationError, OSError) as exc:
            problems.append(Problem(path, describe(exc)))
            continue
        if not (root / "__init__.py").is_file():
            problems.append(Problem(root, "missing __init__.py"))
            continue
        plugins.append(
            GlobalPlugin(
                name=manifest.plugin.name,
                help=manifest.plugin.help,
                root=root,
                commands=manifest.commands,
                panes=manifest.panes,
                builtin=builtin,
            )
        )

    return plugins, problems


def discover_project(
    start: Path | None = None,
) -> tuple[ProjectPlugin | None, list[Problem]]:
    """
    Load the project manifest that applies to `start` (default: CWD).
    """
    found = find_project_manifest(start or Path.cwd())
    if found is None:
        return None, []

    source, data = found
    try:
        manifest = ProjectManifest.model_validate(data)
    except ValidationError as exc:
        return None, [Problem(source, describe(exc))]

    plugin = ProjectPlugin(
        root=source.parent,
        source=source,
        commands=manifest.commands,
        config=manifest.config,
    )
    return plugin, []


def find_project_manifest(start: Path) -> tuple[Path, dict[str, Any]] | None:
    """
    Walk up from `start` looking for `r2.toml`, then `[tool.r2]` in pyproject.toml.

    `r2.toml` wins at every level, so a project can keep both files.
    """
    for directory in [start.resolve(), *start.resolve().parents]:
        path = directory / PROJECT_MANIFEST
        if path.is_file():
            return path, read_toml(path)

        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            table = read_toml(pyproject).get("tool", {}).get("r2")
            if isinstance(table, dict):
                return pyproject, table
    return None


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def describe(exc: Exception) -> str:
    """
    One-line description of a manifest error.
    """
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"]) or "<root>"
            parts.append(f"{loc}: {err['msg']}")
        return "; ".join(parts)
    return str(exc)
