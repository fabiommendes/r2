"""Files that the text of a document names, like `r2/core/links.py`."""

import re
from pathlib import Path

from r2.core import adrs, issues, rfcs
from r2.core.links import LINK_RE
from r2.core.r2_context import find_root

# Folders where a bare file stem names an issue, an ADR or an RFC.
THREAD_FOLDERS = [issues.FOLDER, adrs.FOLDER, rfcs.FOLDER]

STEM_RE = re.compile(r"[\w][\w.-]*")


def resolve_reference(ref: str, document: Path) -> Path | None:
    """The file that ref, written in the file at document, names, if it exists.

    A reference is a path, optionally followed by ":line" or ":start-end",
    relative to the folder of the document or to its project root, or the file
    stem of an issue, an ADR or an RFC of the project.
    """
    ref = ref.strip()
    folder = document.parent
    root = find_root(folder)
    match = LINK_RE.fullmatch(ref)
    if match:
        path = Path(match["path"]).expanduser()
        candidates = [path] if path.is_absolute() else [folder / path, root / path]
    elif STEM_RE.fullmatch(ref):
        candidates = [root / thread / f"{ref}.md" for thread in THREAD_FOLDERS]
    else:
        return None
    return next((path.resolve() for path in candidates if path.is_file()), None)
