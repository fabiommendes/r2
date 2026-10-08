"""
The Rich consoles r2 prints through.

Code reads them as attributes of this module (`console.stdout`), so that
`use_plain` can swap them for plain ones in agent mode.
"""

import rich
from rich.console import Console
from rich.style import Style

style = Style()

# soft_wrap: never fold long lines, agents and pipes want one record per line.
plain = Console(highlight=False, markup=False, emoji=False, style=style, soft_wrap=True)
plain_error = Console(
    stderr=True, highlight=False, markup=False, emoji=False, style=style, soft_wrap=True
)
stdout = Console(highlight=False, style=style, soft_wrap=True)
stderr = Console(stderr=True, highlight=False, style=style, soft_wrap=True)


def use_plain() -> None:
    """
    Print without colors or styles from now on, terminal or not.

    Markup is still parsed, so "[b red]error[/]: x" prints "error: x".
    """
    global stdout, stderr
    stdout = Console(
        color_system=None, emoji=False, highlight=False, style=style, soft_wrap=True
    )
    stderr = Console(
        stderr=True,
        color_system=None,
        emoji=False,
        highlight=False,
        style=style,
        soft_wrap=True,
    )
    rich.reconfigure(color_system=None, highlight=False, emoji=False, soft_wrap=True)
