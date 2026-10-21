"""
Files that the text of a document names, like `r2/core/links.py`.

The one place that decides which file a detected reference names, for the
TUI and for `r2 web` alike. Detection is `r2.core.reports.candidates`.
"""

from pathlib import Path

from r2.core import adrs, issues, rfcs
from r2.core.r2_context import find_root
from r2.core.reports.candidates import code_span_candidate
from r2.core.reports.model import Candidate

# Folders where a bare file stem names an issue, an ADR or an RFC.
THREAD_FOLDERS = [issues.FOLDER, adrs.FOLDER, rfcs.FOLDER]


def targets(candidate: Candidate, folder: Path, root: Path) -> list[Path]:
    """
    The files candidate may name, in the order to try them.

    A path is relative to the folder of the document, then to the project
    root, unless it is absolute or starts at the home folder. A stem names an
    issue, an ADR or an RFC of the project. Nothing here checks the disk.
    """
    if candidate.path is None:
        return []
    if candidate.kind == "stem":
        return [root / thread / f"{candidate.path}.md" for thread in THREAD_FOLDERS]
    if candidate.kind != "path":
        return []
    path = Path(candidate.path).expanduser()
    if path.is_absolute():
        return [path]
    return list(dict.fromkeys([folder / path, root / path]))


def resolve_reference(ref: str, document: Path) -> Path | None:
    """The file that ref, written in the file at document, names, if it exists.

    A reference is a whole code span: a path, optionally followed by a
    locator, or the file stem of an issue, an ADR or an RFC of the project.
    """
    candidate = code_span_candidate(ref.strip())
    if candidate is None:
        return None
    folder = document.parent
    found = targets(candidate, folder, find_root(folder))
    return next((path.resolve() for path in found if path.is_file()), None)
