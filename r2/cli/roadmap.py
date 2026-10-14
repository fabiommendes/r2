#
# `r2 roadmap` and `r2 changelog`: files generated from the milestones of the
# issues. See dev/spec/roadmap.md and dev/spec/cli.md.
#
from pathlib import Path
from typing import Annotated, Any

import typer

from r2.cli.threads import emit_json
from r2.core import issues, roadmap
from r2.core.files import atomic_write
from r2.core.messages import error, success, warn
from r2.core.mode import mode
from r2.core.r2_context import find_root

__all__ = ["changelog", "roadmap_command"]


def roadmap_command(
    check: Annotated[
        bool,
        typer.Option(
            "--check", help="Write nothing; exit with 1 when the file is out of date."
        ),
    ] = False,
) -> None:
    """
    Write ROADMAP.md: the open issues grouped by milestone.
    """
    root = find_root(Path.cwd())
    path = root / roadmap.FILE
    text = roadmap.render_roadmap(roadmap.load(root / issues.FOLDER))
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == text:
        success(f"{roadmap.FILE} is up to date.")
        return
    if check:
        what = "is out of date" if current is not None else "does not exist"
        error(f"{roadmap.FILE} {what}; run r2 roadmap.")
    atomic_write(path, text)
    success(f"Wrote {roadmap.FILE}.")


def changelog(
    draft: Annotated[
        str,
        typer.Option(
            "--draft",
            metavar="MILESTONE",
            help="Print the completed issues of this milestone, grouped by kind.",
        ),
    ],
) -> None:
    """
    Print a changelog draft from the issues of a milestone.
    """
    name = draft.strip()
    found = roadmap.load(find_root(Path.cwd()) / issues.FOLDER)
    known = roadmap.milestones(found)
    error(
        f"No issue has milestone {name!r}; known: {', '.join(known) or 'none'}.",
        name not in known,
    )
    pending = roadmap.open_by_milestone(found).get(name, [])
    warn(
        f"{len(pending)} open issue(s) in {name} left out: "
        + ", ".join(slug for slug, _ in pending)
        + ".",
        bool(pending),
    )
    sections = roadmap.changelog_sections(found, name)
    if mode.json:
        emit_json({"milestone": name, "sections": [to_dict(s) for s in sections]})
        return
    typer.echo(roadmap.render_changelog(name, sections), nl=False)


def to_dict(section: roadmap.Section) -> dict[str, Any]:
    return {
        "title": section.title,
        "issues": [
            {"id": slug, "title": issue.title, "kind": issue.meta.get("kind")}
            for slug, issue in section.issues
        ],
    }
