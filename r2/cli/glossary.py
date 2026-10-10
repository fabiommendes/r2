#
# The `r2 glossary` command group. See dev/spec/cli.md.
#
import json
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from r2.core.files import update
from r2.core.glossary import (
    FIELD_KEY_RE,
    FILE,
    Glossary,
    Term,
    check,
    is_strict,
    parse,
)
from r2.core.messages import error, success
from r2.core.mode import mode
from r2.core.r2_context import find_root

app = typer.Typer(help="Manage the project glossary, GLOSSARY.md.")

file_opt = typer.Option(
    "--file",
    "-f",
    help="Glossary file to work on. Default: GLOSSARY.md at the project root.",
)
tag_opt = typer.Option("--tag", help="Tags, repeatable or comma separated.")
avoid_opt = typer.Option("--avoid", help="Words not to use for this term.")
related_opt = typer.Option("--related", help="Names of related terms.")
code_opt = typer.Option("--code", help="Identifiers or paths in the code.")
field_opt = typer.Option(
    "--field", help="Any other field, as key=value (e.g. pt=termo)."
)

# A plain alias: Typer cannot read `type` statements.
File = Annotated[Path | None, file_opt]


#
# READING
#
@app.command("list")
def list_(
    tag: Annotated[str | None, typer.Option("--tag", help="Only this tag.")] = None,
    file: File = None,
) -> None:
    """
    List the terms, one per line, with the first sentence of each definition.
    """
    terms = read(file).terms
    if tag is not None:
        terms = [t for t in terms if tag.lower() in (x.lower() for x in t.tags)]
    if mode.json:
        emit_json([term.to_dict() for term in terms])
        return
    for term in terms:
        typer.echo(line(term))


@app.command()
def show(
    term: Annotated[str, typer.Argument(help="Name of the term.")],
    file: File = None,
) -> None:
    """
    Print a term as it is written in the glossary.
    """
    path = resolve(file)
    found = read(path).find(term)
    if found is None:
        error(f"No term named {term!r} in {path}.")
        return
    if mode.json:
        emit_json(found.to_dict())
    else:
        typer.echo(found.to_markdown())


@app.command()
def find(
    words: Annotated[list[str], typer.Argument(help="Words to look for.")],
    file: File = None,
) -> None:
    """
    Find the terms that match all the words, including the words to avoid.

    A match on a word to avoid prints "avoided -> Term": the term to use
    instead.
    """
    query = " ".join(words)
    terms = [term for term in read(file).terms if term.matches(query)]
    if mode.json:
        emit_json([{**t.to_dict(), "avoided": t.avoided(query)} for t in terms])
        return
    for term in terms:
        avoided = term.avoided(query)
        for word in avoided:
            typer.echo(f"{word} -> {term.name}")
        if not avoided:
            typer.echo(line(term))


@app.command("check")
def check_(file: File = None) -> None:
    """
    Report problems in the glossary, without changing it. Exit 1 if any.
    """
    path = resolve(file)
    problems = check(read_text(path))
    if mode.json:
        emit_json([{"term": p.term, "problem": p.problem} for p in problems])
    else:
        for problem in problems:
            typer.echo(
                f"{problem.term}: {problem.problem}"
                if problem.term
                else f"{path}: {problem.problem}"
            )
    if problems:
        raise typer.Exit(1)


#
# WRITING
#
@app.command()
def add(
    term: Annotated[str, typer.Argument(help='Term to add, as "name: definition".')],
    tag: Annotated[list[str] | None, tag_opt] = None,
    avoid: Annotated[list[str] | None, avoid_opt] = None,
    related: Annotated[list[str] | None, related_opt] = None,
    code: Annotated[list[str] | None, code_opt] = None,
    field: Annotated[list[str] | None, field_opt] = None,
    file: File = None,
) -> None:
    """
    Add a term to the glossary.

    The definition may be given inline, as "name: definition". When it is
    omitted, it is asked interactively.
    """
    name, _, definition = term.partition(":")
    name, definition = name.strip(), definition.strip()
    error("The term name cannot be empty.", not name)
    fields = field_values(tag, avoid, related, code, field)

    path = resolve(file)
    must_exist(path)
    if not definition:
        error(
            'In agent mode, give the definition inline: "name: definition".', mode.agent
        )
        definition = typer.prompt(f"Definition for {name!r}").strip()
        error("The definition cannot be empty.", not definition)

    def change(doc: Glossary) -> None:
        error(f"{name!r} is already defined in {path}.", doc.find(name) is not None)
        new = Term(name=name, definition=definition)
        apply_fields(new, fields)
        doc.terms.append(new)

    write(path, change)
    success(f"Added {name!r} to {path}.")


@app.command("set")
def set_(
    term: Annotated[str, typer.Argument(help="Name of the term to change.")],
    definition: Annotated[
        str | None, typer.Option("--definition", help="New definition.")
    ] = None,
    tag: Annotated[list[str] | None, tag_opt] = None,
    avoid: Annotated[list[str] | None, avoid_opt] = None,
    related: Annotated[list[str] | None, related_opt] = None,
    code: Annotated[list[str] | None, code_opt] = None,
    field: Annotated[list[str] | None, field_opt] = None,
    unset: Annotated[
        list[str] | None, typer.Option("--unset", help="Field to remove.")
    ] = None,
    file: File = None,
) -> None:
    """
    Change a term. Each field option replaces the whole field.
    """
    fields = field_values(tag, avoid, related, code, field)
    removed = unset or []
    if definition is None and not fields and not removed:
        raise typer.BadParameter("Nothing to change: give a field option.")
    if definition is not None and not definition.strip():
        raise typer.BadParameter("The definition cannot be empty.")

    path = resolve(file)
    must_exist(path)

    def change(doc: Glossary) -> None:
        found = doc.find(term)
        if found is None:
            error(f"No term named {term!r} in {path}.")
            return
        if definition is not None:
            found.definition = definition.strip()
        for key in removed:
            found.fields.pop(key, None)
        apply_fields(found, fields)

    write(path, change)
    success(f"Changed {term!r} in {path}.")


@app.command()
def remove(
    term: Annotated[str, typer.Argument(help="Name of the term to remove.")],
    file: File = None,
) -> None:
    """
    Remove a term from the glossary.
    """
    path = resolve(file)
    must_exist(path)

    def change(doc: Glossary) -> None:
        found = doc.find(term)
        if found is None:
            error(f"No term named {term!r} in {path}.")
            return
        doc.terms.remove(found)

    write(path, change)
    success(f"Removed {term!r} from {path}.")


@app.command()
def fmt(file: File = None) -> None:
    """
    Rewrite the glossary in the strict format, with the terms sorted.

    This is the only command that accepts a file without "type: glossary"
    in its frontmatter, and adds it.
    """
    path = resolve(file)
    must_exist(path)
    update(path, lambda text: parse(text).sorted().to_markdown())
    success(f"Formatted {path}.")


#
# HELPERS
#
def resolve(file: Path | None) -> Path:
    """The glossary file: the one given, or the default at the project root."""
    return file if file is not None else find_root(Path.cwd()) / FILE


def must_exist(path: Path) -> None:
    error(f"Glossary file not found: {path}", not path.is_file())


def read_text(path: Path) -> str:
    must_exist(path)
    return path.read_text(encoding="utf-8", errors="replace")


def read(file: Path | None) -> Glossary:
    return parse(read_text(resolve(file)))


def write(path: Path, change: Callable[[Glossary], None]) -> None:
    """
    Apply change to the glossary in path, under a lock, and save it sorted.

    Refuse a file that does not declare itself a glossary: the strict
    format would rewrite all of it.
    """

    def apply(text: str) -> str:
        error(
            f"{path} has no 'type: glossary' in its frontmatter; "
            "convert it with `r2 glossary fmt` first.",
            not is_strict(text),
        )
        doc = parse(text)
        change(doc)
        return doc.sorted().to_markdown()

    update(path, apply)


def field_values(
    tag: list[str] | None,
    avoid: list[str] | None,
    related: list[str] | None,
    code: list[str] | None,
    field: list[str] | None,
) -> dict[str, str]:
    """The fields given as options, by key, with list entries joined."""
    values: dict[str, list[str]] = {}
    for key, given in [("tags", tag), ("avoid", avoid), ("related", related)]:
        if given is not None:
            values[key] = entries(given)
    if code is not None:
        values["code"] = entries(code)
    for item in field or []:
        key, sep, value = item.partition("=")
        key = key.strip()
        if not sep or FIELD_KEY_RE.fullmatch(key) is None:
            raise typer.BadParameter(
                f"{item!r}: use key=value, with a lowercase key.", param_hint="--field"
            )
        values.setdefault(key, []).extend(entries([value]))
    return {key: ", ".join(items) for key, items in values.items()}


def entries(values: list[str]) -> list[str]:
    """Split comma separated values into stripped, non-empty entries."""
    return [
        item.strip() for value in values for item in value.split(",") if item.strip()
    ]


def apply_fields(term: Term, fields: dict[str, str]) -> None:
    for key, value in fields.items():
        if value:
            term.fields[key] = value
        else:
            term.fields.pop(key, None)


def line(term: Term) -> str:
    return f"{term.name}: {term.summary}" if term.summary else term.name


def emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
