#
# `r2 handoff`: the handoffs in dev/handoffs. See dev/spec/cli.md.
#
from pathlib import Path
from typing import Annotated, Any

import typer

from r2.cli.threads import emit_json, relative
from r2.core import handoffs
from r2.core.messages import error, success
from r2.core.mode import mode

handoff_app = typer.Typer(
    help="Manage the handoffs in dev/handoffs of the main checkout.",
    no_args_is_help=True,
)
ident_help = "File name without .md, or a unique prefix."


@handoff_app.command("list")
def list_(
    all: Annotated[
        bool, typer.Option("--all", "-a", help="Include taken handoffs.")
    ] = False,
) -> None:
    """
    List the open handoffs, the most recent first: id, status, created, title.
    """
    rows = [
        handoff
        for handoff in handoffs.load_all(folder())
        if all or handoff.status != handoffs.TAKEN
    ]
    if mode.json:
        emit_json([to_dict(handoff) for handoff in rows])
        return
    for handoff in rows:
        created = f"{handoff.created:%Y-%m-%dT%H:%M}"
        typer.echo(f"{handoff.id}  {handoff.status}  {created}  {handoff.title}")


@handoff_app.command()
def show(ident: Annotated[str, typer.Argument(help=ident_help)]) -> None:
    """
    Print the handoff file.
    """
    emit(handoffs.load(find(ident)))


@handoff_app.command()
def take(
    ident: Annotated[
        str | None,
        typer.Argument(help=f"{ident_help} Default: the latest open handoff."),
    ] = None,
) -> None:
    """
    Mark an open handoff as taken and print it.
    """
    if ident is None:
        try:
            path = handoffs.latest_open(folder())
        except LookupError as exc:
            error(str(exc).capitalize() + ".")
            raise
    else:
        path = find(ident)
    try:
        handoff = handoffs.take(path)
    except ValueError as exc:
        error(str(exc).capitalize() + ".")
        raise
    emit(handoff)


@handoff_app.command()
def prune(
    days: Annotated[
        int,
        typer.Option("--days", min=0, help="Remove handoffs older than this."),
    ] = handoffs.PRUNE_DAYS,
) -> None:
    """
    Remove the taken handoffs, the old ones and those of closed issues.
    """
    removed = handoffs.prune(folder(), days=days)
    for handoff, reason in removed:
        success(f"Removed {handoff.id} ({reason}).")
    success("Nothing to prune.", not removed)


#
# HELPERS
#
def folder() -> Path:
    return handoffs.folder(Path.cwd())


def find(ident: str) -> Path:
    try:
        return handoffs.find(folder(), ident)
    except LookupError as exc:
        error(str(exc).capitalize() + ".")
        raise


def emit(handoff: handoffs.Handoff) -> None:
    if mode.json:
        emit_json(to_dict(handoff, body=True))
    else:
        text = handoff.path.read_text(encoding="utf-8", errors="replace")
        typer.echo(text, nl=False)


def to_dict(handoff: handoffs.Handoff, body: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": handoff.id,
        "path": str(relative(handoff.path)),
        "title": handoff.title,
        "status": handoff.status,
        "created": f"{handoff.created:%Y-%m-%dT%H:%M}",
        "meta": handoff.meta,
    }
    if body:
        data["body"] = handoff.body
    return data
