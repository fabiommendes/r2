"""Open files in the user's terminal editor."""

import os
import shlex

from robin.links import Link

DEFAULT_EDITOR = "micro"


def editor_command(link: Link) -> list[str]:
    """Build the command that opens link in a terminal editor.

    The editor comes from $ROBIN_EDITOR, $EDITOR, $VISUAL or defaults to
    micro. $EDITOR goes before $VISUAL because $VISUAL often names a GUI
    editor, which would return at once instead of taking over the terminal.

    Most terminal editors (micro, vim, nvim, nano, emacs) accept "+LINE" to
    jump to a line.
    """
    editor = (
        os.environ.get("ROBIN_EDITOR")
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
        or DEFAULT_EDITOR
    )
    command = shlex.split(editor)
    if link.start is not None:
        command.append(f"+{link.start}")
    return [*command, str(link.path)]
