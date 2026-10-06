#
# The `r2 plugins` command group.
#
from __future__ import annotations

import typer

from r2.cli.registry import registry
from r2.core import console
from r2.core.messages import error, success
from r2.core.plugins.loader import PluginError, load_plugin

app = typer.Typer(help="Inspect installed plugins.")


@app.command("list")
def list_() -> None:
    """
    Show the project manifest, global plugins, their commands, and any
    command that lost a name collision.
    """
    out = console.plain
    if registry.project is not None:
        names = ", ".join(registry.project.commands) or "-"
        out.print(f"project  {registry.project.source}  commands: {names}")
    for plugin in registry.globals:
        names = ", ".join(plugin.commands) or "-"
        line = f"global   {plugin.name:<12} {plugin.root}  commands: {names}"
        if plugin.panes:
            line += f"  panes: {', '.join(plugin.panes)}"
        out.print(line)
    for name, kind, reason in registry.shadowed:
        out.print(f"shadowed {kind} command {name!r} (taken by {reason})")
    for problem in registry.problems:
        out.print(f"problem  {problem}")
    if registry.project is None and not registry.globals:
        out.print("no plugins found")


@app.command()
def doctor() -> None:
    """
    Import every global plugin and check that the commands and panes
    declared in plugin.toml exist. Exits 1 on the first failure.
    """
    for problem in registry.problems:
        error(str(problem))

    for plugin in registry.globals:
        try:
            loaded = load_plugin(plugin)
        except PluginError as exc:
            error(str(exc))
            return
        for name in plugin.commands:
            missing = name not in loaded.commands
            error(f"{plugin.name}: {name!r} is in plugin.toml but not defined", missing)
        if plugin.panes or loaded.panes:
            from r2.tui.plugins import load_panes

            _, problems = load_panes([plugin])
            for problem in problems:
                error(f"{plugin.name}: {problem.message}")
        counts = f"{len(plugin.commands)} command(s), {len(plugin.panes)} pane(s)"
        success(f"{plugin.name}: {counts} ok")

    if registry.project is not None:
        success(f"project manifest {registry.project.source} ok")
