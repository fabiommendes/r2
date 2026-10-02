import rich
from typer import Exit


def error(msg: str, /, has_error: bool = True, code: int = 1):
    """
    Print an error message and exit the program.

    Args:
        msg: The error message to display.
        has_error: If False, the function will do nothing.
        code: The exit code to use when exiting the program.
    """
    if not has_error:
        return
    rich.print(f"[b red]error[/]: {msg}")
    raise Exit(code=code)


def warn(msg: str, /, has_warning: bool = True):
    """
    Print a warning message.

    Args:
        msg: The warning message to display.
        has_warning: If False, the function will do nothing.
    """
    if not has_warning:
        return
    rich.print(f"[b yellow]warning[/]: {msg}")


def success(msg: str, /, has_success: bool = True):
    """
    Print a success message.

    Args:
        msg: The success message to display.
        has_success: If False, the function will do nothing.
    """
    if not has_success:
        return
    rich.print(f"[b green]success[/]: {msg}")
