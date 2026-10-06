"""
The `sys` plugin: commands tied to one specific machine setup.

Settings, under `[plugins.sys]` in the r2 config:

    hd = "~/hd"                 # where `r2 hd` moves things to
    aliases = "~/.bash_aliases" # file edited by `r2 alias`
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import rich
import typer
from pydantic import BaseModel

from r2.core.alias import create_alias, parse_sections
from r2.core.editor import edit_file
from r2.core.files import move_to_hd
from r2.core.messages import error, warn
from r2.plugin import Plugin


class SysConfig(BaseModel):
    hd: Path = Path("~/hd")
    aliases: Path = Path("~/.bash_aliases")


plugin = Plugin("sys", config=SysConfig)

ERRORS = {
    "alias-name-required": (
        "Alias name is required when not using --sections, --list, or --edit."
    ),
}


@plugin.command()
def hd(
    file: Annotated[
        Path, typer.Argument(..., help="Path that will be moved to the hard drive")
    ],
) -> None:
    """
    Move a path to the hard drive and leave a symlink in its place.
    """
    move_to_hd(file, plugin.settings.hd.expanduser())


@plugin.command()
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
    """
    Add a shell alias to the aliases file, or list what is there.
    """
    path = plugin.settings.aliases.expanduser()

    if sections or list:
        for header, entries in (section_map := parse_sections(path)).items():
            rich.print(f"[b blue]{header}[/]")
            if list:
                for name, value in entries:
                    rich.print(f"  - [b yellow]{name}[/]=[fg]{value}[/]")
                rich.print()
        if not section_map:
            warn("No alias sections found.")
        return
    elif edit:
        edit_file(path)
    else:
        error(ERRORS["alias-name-required"], not alias)
        create_alias(
            py=py, js=js, package=package, alias=alias, section=section, path=path
        )
