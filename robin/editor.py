"""Open files in the user's terminal editor."""

import os
import shlex

from robin.links import Link

DEFAULT_EDITOR = "micro"


def editor_command(link: Link) -> list[str]:
    """Build the command that opens link in $VISUAL, $EDITOR or micro.

    Most terminal editors (micro, vim, nvim, nano, emacs) accept "+LINE" to
    jump to a line.
    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or DEFAULT_EDITOR
    command = shlex.split(editor)
    if link.start is not None:
        command.append(f"+{link.start}")
    return [*command, str(link.path)]
