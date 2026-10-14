#
# The app object and toplevel CLI commands.
#
from __future__ import annotations

import os
import re
from collections.abc import Container
from pathlib import Path
from typing import Annotated

import typer
from typer.core import TyperGroup

from r2.cli.coverage import app as coverage_app
from r2.cli.glossary import app as glossary_app
from r2.cli.handoffs import handoff_app
from r2.cli.plugins import app as plugins_app
from r2.cli.stories import story_app
from r2.cli.threads import adr_app, issue_app, rfc_app
from r2.core import console
from r2.core.mode import configure
from r2.core.project import get_project

__all__ = ["app", "build_app"]

app = typer.Typer(no_args_is_help=True)


def root(
    ctx: typer.Context,
    agent: Annotated[
        bool,
        typer.Option(
            "--agent",
            envvar="R2_AGENT",
            help="Agent mode: no prompts, summary output, --yes for destructive "
            "commands.",
        ),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="More output; repeat for more."
        ),
    ] = 0,
    quiet: Annotated[
        int,
        typer.Option("--quiet", "-q", count=True, help="Less output; repeat for less."),
    ] = 0,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Pre-approve destructive commands.")
    ] = False,
    json: Annotated[
        bool, typer.Option("--json", help="Print data as JSON, where supported.")
    ] = False,
    directory: Annotated[
        Path | None,
        typer.Option(
            "-C",
            help="Run as if r2 started in this directory.",
            file_okay=False,
            exists=True,
        ),
    ] = None,
) -> None:
    """
    A development assistant for humans and coding agents. With no arguments,
    r2 opens the TUI.

    Global options are accepted after the command name too, except for
    project and plugin commands, which forward their arguments.
    """
    if directory is not None:
        os.chdir(directory)
    if configure(agent=agent, verbose=verbose, quiet=quiet, yes=yes, json=json).agent:
        use_plain_output()
    if ctx.invoked_subcommand is None:
        # Only global options: show the help, as a group without a command does.
        typer.echo(ctx.get_help())
        raise typer.Exit(2)


def use_plain_output() -> None:
    """
    Agent mode output: no colors, boxes or pretty tracebacks, for r2 and
    for every Typer app it runs, plugins included.

    `r2.cli.main` sets the same through the environment before Typer is
    imported, which also covers --help, parsed before this callback runs.
    """
    import typer.core

    typer.core.HAS_RICH = False
    os.environ["TYPER_STANDARD_TRACEBACK"] = "1"
    os.environ.setdefault("NO_COLOR", "1")
    console.use_plain()


app.callback(invoke_without_command=True)(root)


@app.command()
def help(
    ctx: typer.Context,
    all: Annotated[
        bool, typer.Option("--all", "-a", help="Include hidden commands.")
    ] = False,
) -> None:
    """
    List every available command as plain text, one per line.
    """
    from r2.cli.registry import registry

    group = ctx.find_root().command
    assert isinstance(group, TyperGroup)

    rows: list[tuple[str, str]] = []
    for name in sorted(group.commands):
        cmd = group.commands[name]
        if cmd.hidden and not all:
            continue
        tags = ""
        if entry := registry.entries.get(name):
            tags = "".join(f"[{tag}] " for tag in entry.tags)
        summary = (cmd.help or "").strip().splitlines()[0] if cmd.help else ""
        label = f"{name} ..." if isinstance(cmd, TyperGroup) else name
        rows.append((label, tags + summary))

    width = max((len(label) for label, _ in rows), default=0)
    for label, text in rows:
        console.plain.print(f"r2 {label.ljust(width)}  {text}".rstrip())


#
# PROJECT TASKS
#
path_opt = typer.Option(..., "--path", help="Alternate path to search for the project.")


@app.command()
def init(
    path: Annotated[Path | None, path_opt] = None,
    type: Annotated[
        str, typer.Option(..., "--type", "-t", help="Type of project to initialize")
    ] = "lib",
) -> None:
    """
    Initialize a new project.
    """

    project = get_project(path)
    project.docs()


@app.command()
def test(path: Annotated[Path | None, path_opt] = None) -> None:
    """
    Run the default test suite.
    """
    project = get_project(path)
    project.test()


@app.command()
def build(path: Annotated[Path | None, path_opt] = None) -> None:
    """
    Run the default build process.
    """
    project = get_project(path)
    project.build()


@app.command()
def docs(path: Annotated[Path | None, path_opt] = None) -> None:
    """
    Generate project documentation.
    """
    project = get_project(path)
    project.docs()


app.add_typer(coverage_app, name="coverage")
app.add_typer(glossary_app, name="glossary")
app.add_typer(issue_app, name="issue")
app.add_typer(adr_app, name="adr")
app.add_typer(rfc_app, name="rfc")
app.add_typer(handoff_app, name="handoff")
app.add_typer(story_app, name="story")
app.add_typer(plugins_app, name="plugins")


def build_app(
    plugins_dir: Path | None = None, project_start: Path | None = None
) -> typer.Typer:
    """
    The root app with builtin commands plus every discovered plugin command.

    Defaults: plugins from `$R2_CONFIG_DIR/plugins`, project manifest found
    from the current directory.
    """
    from r2.cli.registry import install

    # `add_typer` without a name drops the callback, so rebuild explicitly.
    new = typer.Typer(no_args_is_help=True)
    new.callback(invoke_without_command=True)(root)
    new.registered_commands += app.registered_commands
    new.registered_groups += app.registered_groups
    install(new, plugins_dir=plugins_dir, project_start=project_start)
    return new


#
# GLOBAL OPTIONS
#
GLOBAL_FLAGS = {"--agent", "--verbose", "--quiet", "--yes", "--json"}
GLOBAL_SHORT_RE = re.compile(r"-[vqy]+")


def is_global_flag(arg: str) -> bool:
    return arg in GLOBAL_FLAGS or GLOBAL_SHORT_RE.fullmatch(arg) is not None


def command_index(args: list[str]) -> int | None:
    """The position of the command name: the first argument not an option."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return None
        if arg == "-C":
            index += 2
            continue
        if not arg.startswith("-"):
            return index
        index += 1
    return None


def take_directory(args: list[str]) -> tuple[list[str], Path | None]:
    """
    Remove the -C option given before the command name, returning its value.

    r2 must change directory before it builds the app, since project
    commands are found from the current directory.
    """
    end = command_index(args)
    head = args if end is None else args[:end]
    for index, arg in enumerate(head):
        if arg == "-C" and index + 1 < len(head):
            return args[:index] + args[index + 2 :], Path(args[index + 1])
        if arg.startswith("-C") and len(arg) > 2:
            return args[:index] + args[index + 1 :], Path(arg[2:].removeprefix("="))
    return args, None


def hoist_globals(args: list[str], passthrough: Container[str]) -> list[str]:
    """
    Move the global options that follow the command name before it.

    Commands in passthrough forward their arguments to another program, so
    their arguments are left alone. Nothing after `--` moves.
    """
    start = command_index(args)
    if start is None or args[start] in passthrough:
        return args
    head, rest = args[:start], args[start:]
    moved: list[str] = []
    kept: list[str] = []
    for index, arg in enumerate(rest):
        if arg == "--":
            kept += rest[index:]
            break
        (moved if is_global_flag(arg) else kept).append(arg)
    return head + moved + kept
