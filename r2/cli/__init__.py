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
    if wants_agent(args):
        # Typer reads these when it is imported: plain Click help and
        # errors, and standard tracebacks, with no colors or boxes.
        # NO_COLOR reaches the Consoles plugins create themselves, and the
        # programs r2 runs, whose output an agent reads as text.
        os.environ["TYPER_USE_RICH"] = "0"
        os.environ["TYPER_STANDARD_TRACEBACK"] = "1"
        os.environ.setdefault("NO_COLOR", "1")
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


def wants_agent(args: list[str]) -> bool:
    """Whether the command line or the environment asks for agent mode."""
    from r2.core.mode import AGENT_ENV, env_flag

    head = args[: args.index("--")] if "--" in args else args
    return "--agent" in head or env_flag(AGENT_ENV)
