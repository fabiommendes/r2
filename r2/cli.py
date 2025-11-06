from pathlib import Path
from typing import Annotated

import typer
from rich import print

app = typer.Typer()


@app.command()
def hd(
    file: Annotated[
        Path, typer.Argument(..., help="Path that will be moved to the Hard drive")
    ],
):
    """
    Move path to the hard drive ($HOME/hd) and create a symlink back to it.
    """
    from .files import move_to_hd

    move_to_hd(file)


@app.command()
def help():
    """
    Show help information about the CLI.
    """
    print("Under construction...")


def main():
    """
    Run application.
    """
    app()
