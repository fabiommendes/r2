#
# Command groups for threads: `r2 issue` and `r2 adr`. See dev/spec/cli.md.
#
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from r2.core import adrs, issues
from r2.core.files import create
from r2.core.messages import error, success
from r2.core.mode import mode
from r2.core.r2_context import find_root
from r2.core.threads import AUTHOR_ENV, Comment, Format, Thread, default_author

__all__ = ["AUTHOR_ENV", "adr_app", "author", "issue_app"]

ident_arg = typer.Argument(help="File name without .md, a unique prefix, or a number.")
by_opt = typer.Option(
    "--by", help=f"Author. Default: ${AUTHOR_ENV}, then git user.name."
)
tag_opt = typer.Option("--tag", help="Tags, repeatable or comma separated.")
text_help = "Markdown text, or - to read it from stdin."


def thread_app(fmt: Format[Any], help: str) -> typer.Typer:
    """The commands shared by every kind of thread."""
    app = typer.Typer(help=help)

    @app.command()
    def new(
        title: Annotated[str, typer.Argument(help="Title.")],
        body: Annotated[
            str | None, typer.Option("--body", help=f"Description. {text_help}")
        ] = None,
        tag: Annotated[list[str] | None, tag_opt] = None,
        by: Annotated[str | None, by_opt] = None,
    ) -> None:
        """
        Create a thread and print its path.
        """
        title = title.strip()
        error("The title cannot be empty.", not title)
        meta: dict[str, Any] = {"creator": author(by)}
        if tags := entries(tag or []):
            meta["tags"] = tags
        thread = fmt.new(title, **meta)
        if body is not None:
            thread.description = read_text(body)
        path = create(
            folder(fmt), lambda folder: fmt.new_path(folder, title), fmt.render(thread)
        )
        typer.echo(relative(path))

    @app.command("list")
    def list_(
        status: Annotated[
            list[str] | None, typer.Option("--status", help="Only these statuses.")
        ] = None,
        tag: Annotated[str | None, typer.Option("--tag", help="Only this tag.")] = None,
        all: Annotated[
            bool, typer.Option("--all", "-a", help="Include closed threads.")
        ] = False,
    ) -> None:
        """
        List the open threads: id, status and title, one per line.
        """
        rows = []
        for path, thread in load_all(fmt).items():
            if status and thread.status not in status:
                continue
            if not status and not all and thread.status in fmt.closed:
                continue
            tags = [str(t).lower() for t in thread.meta.get("tags") or []]
            if tag is not None and tag.lower() not in tags:
                continue
            rows.append((path, thread))
        rows.sort(key=lambda row: (fmt.status_order(row[1].status), row[0].stem))
        if mode.json:
            emit_json([to_dict(path, thread) for path, thread in rows])
            return
        for path, thread in rows:
            typer.echo(f"{path.stem}  {thread.status}  {thread.title}")

    @app.command()
    def show(ident: Annotated[str, ident_arg]) -> None:
        """
        Print the thread file.
        """
        path = find(fmt, ident)
        if mode.json:
            emit_json(to_dict(path, load_all(fmt)[path], comments=True))
        else:
            typer.echo(path.read_text(encoding="utf-8", errors="replace"), nl=False)

    @app.command()
    def comment(
        ident: Annotated[str, ident_arg],
        text: Annotated[str, typer.Argument(help=text_help)],
        by: Annotated[str | None, by_opt] = None,
    ) -> None:
        """
        Add a comment at the end of the thread.
        """
        body = read_text(text)
        error("The comment cannot be empty.", not body.strip())
        path = find(fmt, ident)
        name = author(by)
        fmt.edit(path, lambda t: t.comments.append(Comment(body, name or None)))
        success(f"Commented on {path.stem}.")

    @app.command("status")
    def status_(
        ident: Annotated[str, ident_arg],
        status: Annotated[str, typer.Argument(help=", ".join(fmt.statuses))],
    ) -> None:
        """
        Move the thread to a status.
        """
        error(
            f"Unknown status {status!r}; use one of: {', '.join(fmt.statuses)}.",
            status not in fmt.statuses,
        )
        path = find(fmt, ident)
        fmt.edit(path, lambda thread: fmt.set_status(thread, status))
        success(f"{path.stem} is {status}.")

    @app.command()
    def advance(ident: Annotated[str, ident_arg]) -> None:
        """
        Move the thread to the next status of the workflow.
        """
        path = find(fmt, ident)
        moved: list[str] = []

        def step(thread: Thread) -> None:
            if (status := fmt.next_status.get(thread.status)) is not None:
                fmt.set_status(thread, status)
            moved.append(thread.status)

        fmt.edit(path, step)
        success(f"{path.stem} is {moved[0]}.")

    return app


issue_app = thread_app(issues.FORMAT, "Manage the issues in dev/issues.")
adr_app = thread_app(adrs.FORMAT, "Manage the decision records in dev/adr.")


@adr_app.command()
def supersede(
    new: Annotated[str, typer.Argument(help="The ADR that replaces the other.")],
    old: Annotated[str, typer.Argument(help="The ADR it replaces.")],
) -> None:
    """
    Record that one ADR replaces another.
    """
    new_path, old_path = find(adrs.FORMAT, new), find(adrs.FORMAT, old)
    error("An ADR cannot supersede itself.", new_path == old_path)
    # The new ADR first: its supersedes is what counts when the two
    # disagree, so a failure between the writes is reconciled on reading.
    adrs.FORMAT.edit(new_path, lambda adr: adrs.add_supersedes(adr, old_path.stem))
    adrs.FORMAT.edit(old_path, lambda adr: adrs.mark_superseded(adr, new_path.stem))
    success(f"{new_path.stem} supersedes {old_path.stem}.")


#
# HELPERS
#
def author(by: str | None) -> str:
    """The author of a change: --by, then $R2_AUTHOR, then git user.name."""
    return by.strip() if by is not None else default_author(find_root(Path.cwd()))


def folder(fmt: Format[Any]) -> Path:
    return find_root(Path.cwd()) / fmt.folder


def find(fmt: Format[Any], ident: str) -> Path:
    try:
        return fmt.find(folder(fmt), ident)
    except LookupError as exc:
        error(str(exc).capitalize() + ".")
        raise


def load_all(fmt: Format[Any]) -> dict[Path, Thread]:
    """Every thread in the folder, by path, with statuses reconciled."""
    paths = sorted(folder(fmt).glob("*.md"))
    by_stem = {path.stem: fmt.load(path) for path in paths}
    fmt.reconcile(by_stem)
    return {path: by_stem[path.stem] for path in paths}


def read_text(value: str) -> str:
    """value itself, or stdin when value is -."""
    text = sys.stdin.read() if value == "-" else value
    return text.strip("\n")


def entries(values: list[str]) -> list[str]:
    return [
        item.strip() for value in values for item in value.split(",") if item.strip()
    ]


def relative(path: Path) -> Path:
    try:
        return path.relative_to(Path.cwd())
    except ValueError:
        return path


def to_dict(path: Path, thread: Thread, comments: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": path.stem,
        "path": str(relative(path)),
        "title": thread.title,
        "status": thread.status,
        "meta": thread.meta,
    }
    if comments:
        data["description"] = thread.description
        data["comments"] = [
            {"by": comment.author, "text": comment.text} for comment in thread.comments
        ]
    return data


def emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str))
