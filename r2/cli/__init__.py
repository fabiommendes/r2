"""Command line entry point.

This module must stay cheap to import: it must not import Textual, which is
an optional extra and slow to load. The TUI is imported only when it launches.
"""

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


def main() -> None:
    """Run the r2 command: with no arguments, open the TUI."""
    run_tui()
