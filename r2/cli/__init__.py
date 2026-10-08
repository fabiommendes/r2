"""Command line entry point.

This module must stay cheap to import: it imports neither Textual, an
optional extra that is slow to load, nor Typer. The TUI and the Typer app are
imported only when they run.
"""

import os
import sys


def run_tui() -> None:
    """Open the TUI, or explain how to install it when Textual is missing."""
    try:
        from r2.tui.app import main as tui_main
    except ModuleNotFoundError as error:
        if error.name is None or error.name.split(".")[0] not in (
            "textual",
            "textual_image",
        ):
            raise
        sys.exit("The TUI needs the tui extra: uv tool install 'r2-assistant[tui]'")
    tui_main()


def main(argv: list[str] | None = None) -> None:
    """Run the r2 command: with no arguments, open the TUI."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        run_tui()
        return
    from r2.cli.app import build_app, hoist_globals, take_directory
    from r2.cli.registry import registry

    args, directory = take_directory(args)
    if directory is not None:
        try:
            os.chdir(directory)
        except OSError as error:
            sys.exit(f"error: cannot change to {directory}: {error.strerror}")
    app = build_app()
    args = hoist_globals(args, passthrough=registry.entries)
    app(args=args, prog_name="r2")
