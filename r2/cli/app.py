#
# The app object and toplevel CLI commands.
#
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from typer.core import TyperGroup

from r2.cli.glossary import app as glossary_app
from r2.cli.plugins import app as plugins_app
from r2.core import console
from r2.core.mode import configure
from r2.core.tasks import get_project

__all__ = ["app", "build_app"]

app = typer.Typer()


def root(
    agent: Annotated[
        bool,
        typer.Option(
            "--agent",
            envvar="R2_AGENT",
            help="Agent mode: no prompts, reduced output, --yes for destructive "
            "commands.",
        ),
    ] = False,
    full: Annotated[
        bool,
        typer.Option("--full", help="In agent mode, do not reduce command output."),
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Pre-approve destructive commands.")
    ] = False,
) -> None:
    """
    A development assistant for humans and coding agents. With no arguments,
    r2 opens the TUI.
    """
    configure(agent=agent, full=full, yes=yes)


app.callback()(root)


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


app.add_typer(glossary_app, name="glossary")
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
    new = typer.Typer()
    new.callback()(root)
    new.registered_commands += app.registered_commands
    new.registered_groups += app.registered_groups
    install(new, plugins_dir=plugins_dir, project_start=project_start)
    return new
