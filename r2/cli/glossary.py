#
# The `r2 glossary` command group.
#
from pathlib import Path
from typing import Annotated

import typer

from r2.core.glossary import Glossary, Term, parse
from r2.core.messages import error, success

app = typer.Typer(help="Manage a GLOSSARY.md file.")

DEFAULT_FILE = Path("GLOSSARY.md")

file_opt = typer.Option(..., "--file", "-f", help="Glossary file to work on.")


@app.command()
def sort(file: Annotated[Path, file_opt] = DEFAULT_FILE) -> None:
    """
    Sort the glossary terms alphabetically.
    """
    doc = load(file)
    save(file, doc.sorted())
    success(f"Sorted {len(doc.terms)} terms in {file}.")


@app.command()
def add(
    term: Annotated[str, typer.Argument(help='Term to add, as "name: definition".')],
    file: Annotated[Path, file_opt] = DEFAULT_FILE,
) -> None:
    """
    Add a term to the glossary, then sort it.

    The definition may be given inline, as "name: definition". When it is
    omitted, it is asked interactively.
    """
    name, _, definition = term.partition(":")
    name, definition = name.strip(), definition.strip()
    error("The term name cannot be empty.", not name)

    if not definition:
        definition = typer.prompt(f"Definition for {name!r}").strip()
        error("The definition cannot be empty.", not definition)

    doc = load(file)
    error(f"{name!r} is already defined in {file}.", find(doc, name) is not None)

    doc.terms.append(Term(name=name, definition=definition))
    save(file, doc.sorted())
    success(f"Added {name!r} to {file}.")


@app.command()
def remove(
    term: Annotated[str, typer.Argument(help="Name of the term to remove.")],
    file: Annotated[Path, file_opt] = DEFAULT_FILE,
) -> None:
    """
    Remove a term from the glossary, then sort it.
    """
    doc = load(file)
    index = find(doc, term)
    if index is None:
        error(f"No term named {term!r} in {file}.")
        return

    removed = doc.terms.pop(index)
    save(file, doc.sorted())
    success(f"Removed {removed.name!r} from {file}.")


#
# HELPERS
#
def load(path: Path) -> Glossary:
    """
    Read and parse a glossary file, exiting with an error if it cannot be.
    """
    error(f"Glossary file not found: {path}", not path.is_file())
    try:
        return parse(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        error(f"Could not parse {path}: {exc}")
        raise


def save(path: Path, doc: Glossary) -> None:
    """
    Write a glossary back to its markdown file.
    """
    path.write_text(doc.to_markdown(), encoding="utf-8")


def find(doc: Glossary, name: str) -> int | None:
    """
    Index of the term called `name`, compared case-insensitively.
    """
    target = name.strip().lower()
    for index, term in enumerate(doc.terms):
        if term.name.lower() == target:
            return index
    return None
