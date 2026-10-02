#
# The app object and toplevel CLI commands.
#
from pathlib import Path
from typing import Annotated

import rich
import typer
from rich import print

from r2.cli.glossary import app as glossary_app
from r2.core.messages import error, warn
from r2.core.tasks import get_project

app = typer.Typer()
app.add_typer(glossary_app, name="glossary")


ERRORS = {
    "alias-name-required": (
        "Alias name is required when not using --sections, --list, or --edit."
    ),
}


@app.command()
def hd(
    file: Annotated[
        Path, typer.Argument(..., help="Path that will be moved to the Hard drive")
    ],
) -> None:
    """
    Move path to the hard drive (usually, $HOME/hd) and create a symlink back to it.
    """
    from r2.core.files import move_to_hd

    move_to_hd(file)


@app.command()
def alias(
    alias: Annotated[
        str, typer.Argument(help="Alias to add to your shell configuration")
    ] = "",
    py: Annotated[
        bool, typer.Option("--py", "-p", help="Add a uvx Python script alias")
    ] = False,
    js: Annotated[
        bool, typer.Option("--js", "-j", help="Add a npx JavaScript script alias")
    ] = False,
    package: Annotated[str, typer.Option("--from", "-f", help="Source project")] = "",
    section: Annotated[
        str, typer.Option("--section", "-s", help="Section to add the alias to")
    ] = "",
    sections: Annotated[
        bool, typer.Option("--sections", "-S", help="List existing alias sections")
    ] = False,
    list: Annotated[
        bool, typer.Option("--list", "-l", help="List existing aliases and sections")
    ] = False,
    edit: Annotated[
        bool, typer.Option("--edit", "-e", help="Open the alias file in an editor")
    ] = False,
) -> None:
    from r2.core.alias import create_alias, get_path, parse_sections

    if sections or list:
        for section, aliases in (section_map := parse_sections()).items():
            rich.print(f"[b blue]{section}[/]")
            if list:
                for alias, value in aliases:
                    print(f"  - [b yellow]{alias}[/]=[fg]{value}[/]")
                print()
        if not section_map:
            warn("No alias sections found.")
        return
    elif edit:
        from r2.core.editor import edit_file

        edit_file(get_path())
    else:
        error(ERRORS["alias-name-required"], not alias)
        create_alias(py=py, js=js, package=package, alias=alias, section=section)


@app.command()
def help() -> None:
    """
    Show help information about the CLI.
    """
    print("Under construction...")


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
