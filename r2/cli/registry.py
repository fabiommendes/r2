"""
Plugin registry for the CLI: discovers the two plugin tiers and installs their commands
into the root Typer app as lazy stubs.

Name precedence on collision: builtin command > project command > global
plugin command. Shadowed commands are kept for `r2 plugins list`.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import typer

from r2.core import console
from r2.core.messages import error, warn
from r2.core.mode import mode
from r2.core.plugins.discovery import (
    GlobalPlugin,
    Problem,
    ProjectPlugin,
    discover_global,
    discover_project,
)
from r2.core.plugins.loader import PluginError, load_plugin
from r2.core.plugins.manifest import CommandSpec, ProjectCommand

__all__ = ["Entry", "Registry", "install", "registry"]

type Kind = Literal["project", "global"]
type Runner = Callable[[list[str]], None]

#: Lines of output kept when a failing command is summarized.
SUMMARY_TAIL = 30
TIMEOUT_EXIT = 124


@dataclass(frozen=True)
class Entry:
    name: str
    kind: Kind
    spec: CommandSpec
    #: Plugin name for global commands; manifest path for project ones.
    origin: str
    run: Runner

    @property
    def tags(self) -> list[str]:
        tags: list[str] = [self.kind]
        if self.spec.destructive:
            tags.append("destructive")
        if self.spec.interactive:
            tags.append("interactive")
        if self.spec.hidden:
            tags.append("hidden")
        return tags


@dataclass
class Registry:
    entries: dict[str, Entry] = field(default_factory=dict)
    project: ProjectPlugin | None = None
    globals: list[GlobalPlugin] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    #: (command, kind, reason) for commands that lost a name collision.
    shadowed: list[tuple[str, Kind, str]] = field(default_factory=list)

    def clear(self) -> None:
        self.entries.clear()
        self.project = None
        self.globals.clear()
        self.problems.clear()
        self.shadowed.clear()

    def settings_for(self, plugin: str) -> dict[str, Any]:
        """
        `[plugins.<plugin>]` from the global config, updated with
        `[config.<plugin>]` from the project manifest.
        """
        from r2.core.conf import Config

        data = dict(Config().plugins.get(plugin, {}))
        if self.project is not None:
            data.update(self.project.config.get(plugin, {}))
        return data


registry = Registry()


def install(
    app: typer.Typer,
    plugins_dir: Path | None = None,
    project_start: Path | None = None,
) -> Registry:
    """
    Discover plugins and add one stub command per plugin command to `app`.

    Manifest problems are reported as warnings and never abort the CLI.
    """
    registry.clear()
    taken = builtin_names(app)

    project, problems = discover_project(project_start)
    registry.project = project
    registry.problems += problems

    if project is not None:
        for name, spec in project.commands.items():
            if name in taken:
                registry.shadowed.append((name, "project", "builtin command"))
                continue
            entry = Entry(
                name,
                "project",
                spec,
                str(project.source),
                run_project(project, name, spec),
            )
            add_stub(app, entry)
            taken.add(name)

    globals_, problems = discover_global(plugins_dir)
    registry.globals = globals_
    registry.problems += problems

    for plugin in globals_:
        for name, gspec in plugin.commands.items():
            if name in taken:
                reason = (
                    "builtin command"
                    if name not in registry.entries
                    else "project command"
                )
                registry.shadowed.append((name, "global", reason))
                continue
            entry = Entry(
                name, "global", gspec, plugin.name, run_global(plugin, name, gspec)
            )
            add_stub(app, entry)
            taken.add(name)

    for problem in registry.problems:
        warn(f"plugin skipped: {problem}")

    return registry


def builtin_names(app: typer.Typer) -> set[str]:
    names: set[str] = set()
    for cmd in app.registered_commands:
        names.add(cmd.name or cmd.callback.__name__.replace("_", "-"))  # type: ignore[union-attr]
    for group in app.registered_groups:
        if group.name:
            names.add(group.name)
    return names


def add_stub(app: typer.Typer, entry: Entry) -> None:
    """
    Register a command that forwards every argument, including --help, to
    the plugin's runner. Nothing from the plugin is imported until then.
    """
    registry.entries[entry.name] = entry

    @app.command(
        entry.name,
        help=entry.spec.help,
        hidden=entry.spec.hidden,
        add_help_option=False,
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def stub(ctx: typer.Context) -> None:
        guard_destructive(entry)
        entry.run(list(ctx.args))


def guard_destructive(entry: Entry) -> None:
    """
    In agent mode a destructive command needs an explicit --yes.
    """
    if entry.spec.destructive and mode.agent and not mode.yes:
        error(
            f"{entry.name!r} is destructive; re-run with `r2 --yes {entry.name}`.",
            code=2,
        )


#
# Runners
#
def run_global(plugin: GlobalPlugin, name: str, spec: CommandSpec) -> Runner:
    def run(args: list[str]) -> None:
        try:
            loaded = load_plugin(plugin)
        except PluginError as exc:
            error(str(exc))
            return
        fn = loaded.commands.get(name)
        if fn is None:
            error(
                f"plugin {plugin.name!r} declares {name!r} in plugin.toml "
                "but defines no such command."
            )
            return
        cli = typer.Typer(add_completion=False)
        cli.command(name, help=spec.help)(fn)
        cli(args=args, prog_name=f"r2 {name}")

    return run


def run_project(project: ProjectPlugin, name: str, spec: ProjectCommand) -> Runner:
    def run(args: list[str]) -> None:
        if args and spec.args == "none":
            error(f"{name!r} takes no arguments.", code=2)

        cmd = spec.run
        if args:
            cmd += " " + shlex.join(args)

        summarize = mode.summarize and spec.output == "summary"
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=project.root / spec.cwd,
                env={**os.environ, **spec.env},
                stdin=None if spec.interactive else subprocess.DEVNULL,
                timeout=spec.timeout,
                capture_output=summarize,
                text=True,
                check=False,
            )
        except subprocess.TimeoutExpired:
            error(f"{name!r} timed out after {spec.timeout}s.", code=TIMEOUT_EXIT)
            raise

        if summarize:
            report_summary(name, result)
        raise SystemExit(result.returncode)

    return run


def report_summary(name: str, result: subprocess.CompletedProcess[str]) -> None:
    """
    One line on success; exit code plus the last lines of output on failure.
    """
    if result.returncode == 0:
        console.plain.print(f"ok: {name}")
        return

    console.plain_error.print(f"failed: {name} (exit {result.returncode})")
    lines = (result.stdout + result.stderr).splitlines()
    if len(lines) > SUMMARY_TAIL:
        console.plain_error.print(
            f"... {len(lines) - SUMMARY_TAIL} lines omitted (use --full)"
        )
        lines = lines[-SUMMARY_TAIL:]
    for line in lines:
        console.plain_error.print(line)
