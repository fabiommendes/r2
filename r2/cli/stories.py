#
# `r2 story`: the user stories in docs/user-stories and their e2e tests. See
# dev/spec/stories.md and dev/spec/cli.md.
#
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Annotated, Any

import typer

from r2.cli.threads import emit_json, entries, read_text
from r2.core.files import update
from r2.core.messages import error, success, warn
from r2.core.mode import SUMMARY, mode
from r2.core.stories import check as checks
from r2.core.stories.doc import (
    KNOWN_STATUSES,
    Story,
    StoryFile,
    is_strict,
    parse,
    parse_id,
)
from r2.core.stories.tests import StoryTest

story_app = typer.Typer(
    help="Manage the user stories in docs/user-stories and check their e2e tests.",
    no_args_is_help=True,
)

id_help = 'Story id, "role: slug", or "role: title".'
dir_opt = typer.Option(
    "--dir",
    help="Folder of the story files. Default: [config.stories] dir in the "
    "project manifest, or docs/user-stories.",
)
status_opt = typer.Option("--status", help=f"One of {', '.join(KNOWN_STATUSES)}.")
url_opt = typer.Option("--url", help="The page the story happens on.")
related_opt = typer.Option(
    "--relatedTo", help="Related issues and ADRs, repeatable or comma separated."
)
body_opt = typer.Option(
    "--body", help="The narrative. Markdown text, or - to read it from stdin."
)
section_opt = typer.Option("--section", help="Section (level 2 heading).")

# A plain alias: Typer cannot read `type` statements.
Dir = Annotated[Path | None, dir_opt]


#
# READING
#
@story_app.command("list")
def list_(
    role: Annotated[str | None, typer.Option("--role", help="Only this role.")] = None,
    status: Annotated[
        str | None, typer.Option("--status", help="Only this status.")
    ] = None,
    dir: Dir = None,
) -> None:
    """
    List the stories, one per line: id, status, title.
    """
    refs = [
        ref
        for ref in story_refs(dir)
        if (role is None or ref.role == role)
        and (status is None or ref.story.status == status)
    ]
    if mode.json:
        emit_json([to_dict(ref) for ref in refs])
        return
    for ref in refs:
        typer.echo(f"{ref.id}  {ref.story.status}  {ref.story.title}")


@story_app.command()
def show(
    ident: Annotated[str, typer.Argument(help=id_help)],
    dir: Dir = None,
) -> None:
    """
    Print a story in the strict format.
    """
    role, slug = split_id(ident)
    found = next(
        (ref for ref in story_refs(dir) if ref.role == role and ref.story.slug == slug),
        None,
    )
    if found is None:
        error(f"No story {role}: {slug}.")
        return
    if mode.json:
        emit_json(to_dict(found))
    else:
        typer.echo(found.story.to_markdown())


@story_app.command("check")
def check_(
    no_duplicates: Annotated[
        bool,
        typer.Option("--no-duplicates", help="Each story has at most one test."),
    ] = False,
    missing: Annotated[
        bool, typer.Option("--missing", help="Only list the stories no test cites.")
    ] = False,
    covered: Annotated[
        bool, typer.Option("--covered", help="Only list the stories a test cites.")
    ] = False,
    stale: Annotated[
        bool,
        typer.Option(
            "--stale", help="Only list the tests that cite no existing story."
        ),
    ] = False,
    tests: Annotated[
        list[Path] | None,
        typer.Option(
            "--tests",
            help="E2e test file or folder, repeatable. Default: [config.stories] "
            "tests in the project manifest, or test/stories or tests/stories.",
        ),
    ] = None,
    dir: Dir = None,
) -> None:
    """
    Check that stories and e2e tests cite each other. Exit 1 on errors.

    Errors: an implemented or partial story without a test, a test that cites
    no story or one that does not exist, two stories with the same id. A test
    of a todo story is a warning. --missing, --covered and --stale only list.
    """
    if missing + covered + stale > 1:
        raise typer.BadParameter("Give only one of --missing, --covered, --stale.")
    where = layout(dir, tests or [])
    report = checks.run(where, no_duplicates)
    if missing or covered:
        refs = report.missing() if missing else report.covered()
        if mode.json:
            emit_json(
                [{**to_dict(ref), "tests": tests_of(report, ref)} for ref in refs]
            )
            return
        for ref in refs:
            typer.echo(f"{ref.id}  {ref.story.status}  {ref.story.title}")
        return
    if stale:
        found = report.stale()
        if mode.json:
            emit_json([test_dict(test) for test in found])
            return
        for test in found:
            typer.echo(f"{test.location}  {test.name}")
        return

    if not where.tests:
        warn("No e2e test folder found; give --tests or set [config.stories] tests.")
    for problem in report.warnings:
        warn(str(problem))
    if mode.json:
        emit_json(
            {
                "errors": [problem_dict(p) for p in report.errors],
                "warnings": [problem_dict(p) for p in report.warnings],
                "coverage": report.coverage(),
            }
        )
    else:
        for problem in report.errors:
            typer.echo(str(problem))
        if mode.verbosity >= SUMMARY:
            for row in report.coverage():
                typer.echo(
                    f"{row['role']}: {row['tested']} of {row['stories']} stories "
                    f"have a test ({row['need_test']} implemented or partial)"
                )
    if report.errors:
        raise typer.Exit(1)


#
# WRITING
#
@story_app.command()
def new(
    ident: Annotated[str, typer.Argument(help='The story, as "role: Title".')],
    section: Annotated[str | None, section_opt] = None,
    status: Annotated[str | None, status_opt] = None,
    url: Annotated[str | None, url_opt] = None,
    related: Annotated[list[str] | None, related_opt] = None,
    body: Annotated[str | None, body_opt] = None,
    dir: Dir = None,
) -> None:
    """
    Add a story to the file of its role, creating the file if needed.

    Without --section, the story goes to the last section of the file.
    """
    role, title = split_title(ident)
    check_status(status)
    meta = new_meta(status, url, related)
    narrative = read_text(body) if body is not None else ""
    path = role_path(dir, role)

    def change(doc: StoryFile) -> None:
        story = Story(title=title, narrative=narrative, meta=meta)
        error(
            f"{role}: {story.slug} already exists in {path}.",
            bool(doc.find(story.slug)),
        )
        if section is not None:
            target = doc.section(section)
        elif doc.sections:
            target = doc.sections[-1]
        else:
            target = doc.section("")
        target.stories.append(story)

    write(path, role, change)
    success(f"Added {story_label(role, title)} to {path}.")


@story_app.command("set")
def set_(
    ident: Annotated[str, typer.Argument(help=id_help)],
    title: Annotated[str | None, typer.Option("--title", help="New title.")] = None,
    section: Annotated[
        str | None, typer.Option("--section", help="Move to this section.")
    ] = None,
    status: Annotated[str | None, status_opt] = None,
    url: Annotated[str | None, url_opt] = None,
    related: Annotated[list[str] | None, related_opt] = None,
    body: Annotated[str | None, body_opt] = None,
    unset: Annotated[
        list[str] | None, typer.Option("--unset", help="Metadata key to remove.")
    ] = None,
    dir: Dir = None,
) -> None:
    """
    Change a story. --relatedTo replaces the whole list.
    """
    role, slug = split_id(ident)
    check_status(status)
    meta = new_meta(status, url, related)
    removed = unset or []
    if title is not None and not title.strip():
        raise typer.BadParameter("The title cannot be empty.")
    if title is None and section is None and body is None and not meta and not removed:
        raise typer.BadParameter("Nothing to change: give an option.")
    narrative = read_text(body) if body is not None else None
    path = role_path(dir, role)
    must_exist(path)

    def change(doc: StoryFile) -> None:
        story = doc.find(slug)
        if story is None:
            error(f"No story {role}: {slug} in {path}.")
            return
        if title is not None:
            other = doc.find(Story(title.strip()).slug)
            error(
                f"{story_label(role, title)} already exists in {path}.",
                other is not None and other is not story,
            )
            story.title = title.strip()
        if section is not None:
            doc.remove(story)
            doc.section(section).stories.append(story)
        if narrative is not None:
            story.narrative = narrative
        for key in removed:
            story.meta.pop(key, None)
        story.meta.update(meta)

    write(path, role, change)
    success(f"Changed {role}: {slug} in {path}.")


@story_app.command()
def remove(
    ident: Annotated[str, typer.Argument(help=id_help)],
    dir: Dir = None,
) -> None:
    """
    Remove a story.
    """
    role, slug = split_id(ident)
    path = role_path(dir, role)
    must_exist(path)

    def change(doc: StoryFile) -> None:
        story = doc.find(slug)
        if story is None:
            error(f"No story {role}: {slug} in {path}.")
            return
        doc.remove(story)

    write(path, role, change)
    success(f"Removed {role}: {slug} from {path}.")


@story_app.command()
def fmt(
    roles: Annotated[
        list[str] | None, typer.Argument(help="Roles to format. Default: all.")
    ] = None,
    dir: Dir = None,
) -> None:
    """
    Rewrite story files in the strict format.

    This is the only command that accepts a file without "type: stories" in
    its frontmatter, and adds it.
    """
    files = checks.load(stories_dir(dir))
    wanted = set(roles or [])
    for name in wanted - {doc.role for doc in files.values()}:
        error(f"No story file for role {name!r}.")
    for path, doc in files.items():
        if wanted and doc.role not in wanted:
            continue
        update(path, partial(reformat, role=path.stem))
        success(f"Formatted {path}.")


#
# HELPERS
#
def reformat(text: str, role: str) -> str:
    return parse(text, role).to_markdown()


def layout(dir: Path | None, tests: list[Path]) -> checks.Layout:
    where = checks.layout(Path.cwd(), dir, tests)
    error(f"Stories folder not found: {where.stories}", not where.stories.is_dir())
    return where


def stories_dir(dir: Path | None) -> Path:
    return layout(dir, []).stories


def story_refs(dir: Path | None) -> list[checks.StoryRef]:
    return [
        checks.StoryRef(path, doc.role, section.name, story)
        for path, doc in checks.load(stories_dir(dir)).items()
        for section in doc.sections
        for story in section.stories
    ]


def role_path(dir: Path | None, role: str) -> Path:
    """The file of role: the one whose role it is, or `<role>.md`."""
    where = checks.layout(Path.cwd(), dir).stories
    for path, doc in checks.load(where).items():
        if doc.role == role:
            return path
    return where / f"{role}.md"


def split_id(ident: str) -> tuple[str, str]:
    parsed = parse_id(ident)
    if parsed is None:
        raise typer.BadParameter(f'{ident!r}: use "role: title".')
    return parsed


def split_title(ident: str) -> tuple[str, str]:
    """The role and title of "role: Title"."""
    split_id(ident)
    role, _, title = ident.partition(":")
    return role.strip(), title.strip()


def check_status(status: str | None) -> None:
    if status is not None and status not in KNOWN_STATUSES:
        raise typer.BadParameter(
            f"{status!r}: use one of {', '.join(KNOWN_STATUSES)}.",
            param_hint="--status",
        )


def new_meta(
    status: str | None, url: str | None, related: list[str] | None
) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if status is not None:
        meta["status"] = status
    if url is not None:
        meta["url"] = url
    if related is not None:
        meta["relatedTo"] = entries(related)
    return meta


def must_exist(path: Path) -> None:
    error(f"Story file not found: {path}", not path.is_file())


def write(path: Path, role: str, change: Callable[[StoryFile], None]) -> None:
    """
    Apply change to the story file at path, under a lock, and save it. A
    missing file starts empty; a file without "type: stories" is refused,
    since the strict format would rewrite all of it.
    """

    def apply(text: str) -> str:
        error(
            f"{path} has no 'type: stories' in its frontmatter; "
            "convert it with `r2 story fmt` first.",
            bool(text.strip()) and not is_strict(text),
        )
        doc = parse(text, role) if text.strip() else StoryFile(role=role)
        change(doc)
        return doc.to_markdown()

    path.parent.mkdir(parents=True, exist_ok=True)
    update(path, apply)


def story_label(role: str, title: str) -> str:
    return f"{role}: {Story(title.strip()).slug}"


def to_dict(ref: checks.StoryRef) -> dict[str, Any]:
    return {
        "id": ref.id,
        "role": ref.role,
        "section": ref.section,
        "title": ref.story.title,
        "status": ref.story.status,
        "meta": ref.story.meta,
        "narrative": ref.story.narrative,
        "path": str(ref.path),
    }


def tests_of(report: checks.Report, ref: checks.StoryRef) -> list[str]:
    return [test.location for test in report.tests_of.get(ref.id, [])]


def test_dict(test: StoryTest) -> dict[str, Any]:
    return {
        "path": test.path,
        "line": test.line,
        "name": test.name,
        "cites": test.cites,
    }


def problem_dict(problem: checks.Problem) -> dict[str, str]:
    return {
        "kind": problem.kind,
        "subject": problem.subject,
        "message": problem.message,
    }
