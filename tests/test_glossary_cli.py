"""
Tests for the `r2 glossary` command group.

These drive the Typer app in-process with Typer's own CliRunner rather than
through `tests.support.run_r2`. The glossary commands are plain file edits --
unlike the project tasks in test_pyproject_tasks.py they never reach
`os.execvpe` -- so there is nothing to gain from a subprocess, and running
in-process keeps the suite fast and lets `add` be fed a prompt answer on
stdin.

Every test works on a GLOSSARY.md written into pytest's `tmp_path`, and
asserts on what is actually on disk afterwards.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.glossary import app as glossary_app
from r2.core.glossary import parse

runner = CliRunner()

SAMPLE = """# Glossary of Terms

Words used across this project.

---

## Widget

A thing that does the thing.

## Doohickey

Like a widget, but worse.
"""


@pytest.fixture
def glossary_file(tmp_path: Path) -> Path:
    path = tmp_path / "GLOSSARY.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def names(path: Path) -> list[str]:
    return [term.name for term in parse(path.read_text(encoding="utf-8")).terms]


def run(*args: str, input: str | None = None):
    return runner.invoke(glossary_app, list(args), input=input)


#
# sort
#
def test_sort_orders_the_terms(glossary_file: Path) -> None:
    result = run("sort", "-f", str(glossary_file))
    assert result.exit_code == 0, result.output
    assert names(glossary_file) == ["Doohickey", "Widget"]


def test_sort_keeps_the_title_and_the_intro(glossary_file: Path) -> None:
    run("sort", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.title == "Glossary of Terms"
    assert doc.intro == "Words used across this project."


def test_sort_keeps_the_definitions(glossary_file: Path) -> None:
    run("sort", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.terms[0].definition == "Like a widget, but worse."
    assert doc.terms[1].definition == "A thing that does the thing."


def test_sort_is_idempotent(glossary_file: Path) -> None:
    run("sort", "-f", str(glossary_file))
    once = glossary_file.read_text(encoding="utf-8")
    run("sort", "-f", str(glossary_file))
    assert glossary_file.read_text(encoding="utf-8") == once


def test_long_and_short_file_options_are_equivalent(glossary_file: Path) -> None:
    assert run("sort", "--file", str(glossary_file)).exit_code == 0
    assert run("sort", "-f", str(glossary_file)).exit_code == 0


def test_the_file_defaults_to_glossary_md(
    glossary_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(glossary_file.parent)
    result = run("sort")
    assert result.exit_code == 0, result.output
    assert names(Path("GLOSSARY.md")) == ["Doohickey", "Widget"]


def test_a_missing_file_is_an_error(tmp_path: Path) -> None:
    result = run("sort", "-f", str(tmp_path / "nope.md"))
    assert result.exit_code != 0
    assert "not found" in result.output


def test_an_unparseable_file_is_an_error_and_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text("not a glossary at all\n", encoding="utf-8")

    result = run("sort", "-f", str(path))

    assert result.exit_code != 0
    assert path.read_text(encoding="utf-8") == "not a glossary at all\n"


#
# add
#
def test_add_takes_an_inline_definition(glossary_file: Path) -> None:
    result = run("add", "Gizmo: A fancy widget.", "-f", str(glossary_file))
    assert result.exit_code == 0, result.output

    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert (
        doc.terms[1]
        == parse("# Glossary\n\n---\n\n## Gizmo\n\nA fancy widget.\n").terms[0]
    )


def test_add_sorts_the_glossary(glossary_file: Path) -> None:
    run("add", "Gizmo: A fancy widget.", "-f", str(glossary_file))
    assert names(glossary_file) == ["Doohickey", "Gizmo", "Widget"]


def test_add_prompts_when_no_definition_is_given(glossary_file: Path) -> None:
    result = run("add", "Gizmo", "-f", str(glossary_file), input="A fancy widget.\n")
    assert result.exit_code == 0, result.output

    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.terms[1].definition == "A fancy widget."


def test_add_prompts_when_the_definition_is_blank(glossary_file: Path) -> None:
    result = run("add", "Gizmo:   ", "-f", str(glossary_file), input="Prompted.\n")
    assert result.exit_code == 0, result.output
    assert parse(glossary_file.read_text(encoding="utf-8")).terms[1].definition == (
        "Prompted."
    )


def test_add_keeps_colons_inside_the_definition(glossary_file: Path) -> None:
    run("add", "Ratio: this: that", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.terms[1].name == "Ratio"
    assert doc.terms[1].definition == "this: that"


def test_add_strips_whitespace_around_the_name_and_definition(
    glossary_file: Path,
) -> None:
    run("add", "  Gizmo  :   A fancy widget.  ", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.terms[1].name == "Gizmo"
    assert doc.terms[1].definition == "A fancy widget."


def test_add_keeps_the_title_and_the_intro(glossary_file: Path) -> None:
    run("add", "Gizmo: A fancy widget.", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.title == "Glossary of Terms"
    assert doc.intro == "Words used across this project."


def test_add_rejects_a_duplicate_term(glossary_file: Path) -> None:
    result = run("add", "widget: Another one.", "-f", str(glossary_file))
    assert result.exit_code != 0
    assert "already defined" in result.output
    assert names(glossary_file) == ["Widget", "Doohickey"]


def test_add_rejects_an_empty_name(glossary_file: Path) -> None:
    result = run("add", ": A definition.", "-f", str(glossary_file))
    assert result.exit_code != 0
    assert names(glossary_file) == ["Widget", "Doohickey"]


def test_add_rejects_an_empty_prompted_definition(glossary_file: Path) -> None:
    result = run("add", "Gizmo", "-f", str(glossary_file), input="\n")
    assert result.exit_code != 0
    assert names(glossary_file) == ["Widget", "Doohickey"]


#
# remove
#
def test_remove_deletes_the_term(glossary_file: Path) -> None:
    result = run("remove", "Widget", "-f", str(glossary_file))
    assert result.exit_code == 0, result.output
    assert names(glossary_file) == ["Doohickey"]


def test_remove_matches_the_name_case_insensitively(glossary_file: Path) -> None:
    assert run("remove", "wIdGeT", "-f", str(glossary_file)).exit_code == 0
    assert names(glossary_file) == ["Doohickey"]


def test_remove_sorts_the_glossary(glossary_file: Path) -> None:
    run("add", "Gizmo: A fancy widget.", "-f", str(glossary_file))
    run("remove", "Doohickey", "-f", str(glossary_file))
    assert names(glossary_file) == ["Gizmo", "Widget"]


def test_remove_keeps_the_title_and_the_intro(glossary_file: Path) -> None:
    run("remove", "Widget", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.title == "Glossary of Terms"
    assert doc.intro == "Words used across this project."


def test_remove_can_empty_the_glossary(glossary_file: Path) -> None:
    run("remove", "Widget", "-f", str(glossary_file))
    run("remove", "Doohickey", "-f", str(glossary_file))
    assert names(glossary_file) == []


def test_remove_rejects_an_unknown_term(glossary_file: Path) -> None:
    result = run("remove", "Nonexistent", "-f", str(glossary_file))
    assert result.exit_code != 0
    assert "No term named" in result.output
    assert names(glossary_file) == ["Widget", "Doohickey"]
