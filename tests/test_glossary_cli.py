"""
Tests for the `r2 glossary` command group (dev/spec/cli.md).

These drive the root Typer app in-process with Typer's own CliRunner rather
than through `tests.support.run_r2`. The glossary commands are plain file
edits -- unlike the project tasks in test_pyproject_tasks.py they never
reach `os.execvpe` -- so there is nothing to gain from a subprocess, and
running in-process keeps the suite fast and lets `add` be fed a prompt
answer on stdin. Going through the root app keeps the global options
(--agent, --json, -q) in play.

Every test works on a GLOSSARY.md written into pytest's `tmp_path`, and
asserts on what is actually on disk afterwards.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import app
from r2.core.glossary import parse

runner = CliRunner()

SAMPLE = """---
type: glossary
status: active
---

# Glossary of Terms

Words used across this project.

---

## Widget

A thing that does the thing. It has parts.

- tags: core
- avoid: gadget, thingamajig
- related: Doohickey

## Doohickey

Like a widget, but worse.
"""


@pytest.fixture(autouse=True)
def _human_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("R2_AGENT", raising=False)


@pytest.fixture
def glossary_file(tmp_path: Path) -> Path:
    path = tmp_path / "GLOSSARY.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return path


def names(path: Path) -> list[str]:
    return [term.name for term in parse(path.read_text(encoding="utf-8")).terms]


def run(*args: str, input: str | None = None):
    """Run `r2 [globals] glossary <command> ...`; globals are leading --x."""
    lead = [arg for arg in args if arg in {"--agent", "--json", "-q", "-qq"}]
    rest = [arg for arg in args if arg not in lead]
    return runner.invoke(app, [*lead, "glossary", *rest], input=input)


def term(path: Path, name: str):
    found = parse(path.read_text(encoding="utf-8")).find(name)
    assert found is not None
    return found


#
# file option
#
def test_long_and_short_file_options_are_equivalent(glossary_file: Path) -> None:
    assert run("list", "--file", str(glossary_file)).exit_code == 0
    assert run("list", "-f", str(glossary_file)).exit_code == 0


def test_the_file_defaults_to_glossary_md_at_the_project_root(
    glossary_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (glossary_file.parent / ".git").mkdir()
    sub = glossary_file.parent / "deep" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    result = run("list")
    assert result.exit_code == 0, result.output
    assert "Widget" in result.output


def test_a_missing_file_is_an_error(tmp_path: Path) -> None:
    result = run("list", "-f", str(tmp_path / "nope.md"))
    assert result.exit_code == 1
    assert "not found" in result.output


#
# list, show, find
#
def test_list_prints_names_and_first_sentences(glossary_file: Path) -> None:
    result = run("list", "-f", str(glossary_file))
    assert result.output.splitlines() == [
        "Widget: A thing that does the thing.",
        "Doohickey: Like a widget, but worse.",
    ]


def test_list_filters_by_tag_ignoring_case(glossary_file: Path) -> None:
    result = run("list", "--tag", "CORE", "-f", str(glossary_file))
    assert result.output.splitlines() == ["Widget: A thing that does the thing."]


def test_list_json(glossary_file: Path) -> None:
    result = run("--json", "list", "-f", str(glossary_file))
    data = json.loads(result.output)
    assert data[0] == {
        "name": "Widget",
        "definition": "A thing that does the thing. It has parts.",
        "fields": {
            "tags": "core",
            "avoid": "gadget, thingamajig",
            "related": "Doohickey",
        },
    }


def test_list_reads_any_markdown(tmp_path: Path) -> None:
    path = tmp_path / "loose.md"
    path.write_text("Some notes.\n\n## Beta\n\nb\n")
    assert run("list", "-f", str(path)).output == "Beta: b\n"


def test_show_prints_the_section(glossary_file: Path) -> None:
    result = run("show", "widget", "-f", str(glossary_file))
    assert result.output.startswith("## Widget\n\nA thing")
    assert "- avoid: gadget, thingamajig" in result.output


def test_show_rejects_an_unknown_term(glossary_file: Path) -> None:
    result = run("show", "Nope", "-f", str(glossary_file))
    assert result.exit_code == 1
    assert "No term named" in result.output


def test_find_matches_definitions(glossary_file: Path) -> None:
    result = run("find", "worse", "-f", str(glossary_file))
    assert result.output == "Doohickey: Like a widget, but worse.\n"


def test_find_points_from_an_avoided_word_to_the_term(glossary_file: Path) -> None:
    result = run("find", "gadg", "-f", str(glossary_file))
    assert result.output == "gadget -> Widget\n"


def test_find_json_lists_the_avoided_words(glossary_file: Path) -> None:
    result = run("--json", "find", "gadget", "-f", str(glossary_file))
    [found] = json.loads(result.output)
    assert (found["name"], found["avoided"]) == ("Widget", ["gadget"])


def test_find_without_matches_is_not_an_error(glossary_file: Path) -> None:
    result = run("find", "zzz", "-f", str(glossary_file))
    assert (result.exit_code, result.output) == (0, "")


#
# check
#
def test_check_passes_a_clean_glossary(glossary_file: Path) -> None:
    result = run("check", "-f", str(glossary_file))
    assert (result.exit_code, result.output) == (0, "")


def test_check_reports_problems_and_exits_1(tmp_path: Path) -> None:
    path = tmp_path / "G.md"
    path.write_text(
        "## A\n\na\n\n- avoid: b\n- related: Nope\n\n## B\n\nb\n\n## a\n\nagain\n"
    )
    result = run("check", "-f", str(path))
    assert result.exit_code == 1
    assert result.output.splitlines() == [
        f"{path}: the frontmatter lacks type: glossary",
        "a: is defined twice",
        "A: avoids 'b', which is the term B",
        "A: relates to 'Nope', which is no term",
    ]


def test_check_json(tmp_path: Path) -> None:
    path = tmp_path / "G.md"
    path.write_text("## A\n\na\n")
    result = run("--json", "check", "-f", str(path))
    assert json.loads(result.output) == [
        {"term": None, "problem": "the frontmatter lacks type: glossary"}
    ]


#
# write guard and fmt
#
def test_writes_refuse_a_file_that_is_not_a_glossary(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("# Readme\n\n## Install\n\nRun it.\n")
    for args in (
        ["add", "X: y"],
        ["remove", "Install"],
        ["set", "Install", "--tag", "t"],
    ):
        result = run(*args, "-f", str(path))
        assert result.exit_code == 1, args
        assert "r2 glossary fmt" in result.output
    assert path.read_text() == "# Readme\n\n## Install\n\nRun it.\n"


def test_fmt_converts_and_sorts(tmp_path: Path) -> None:
    path = tmp_path / "loose.md"
    path.write_text("Some notes.\n\n## Beta\n\nb\n\n## Alpha\n\na\n")

    assert run("fmt", "-f", str(path)).exit_code == 0

    text = path.read_text()
    assert text.startswith("---\ntype: glossary\n")
    assert names(path) == ["Alpha", "Beta"]
    assert parse(text).intro == "Some notes."


def test_fmt_is_idempotent(glossary_file: Path) -> None:
    run("fmt", "-f", str(glossary_file))
    once = glossary_file.read_text()
    run("fmt", "-f", str(glossary_file))
    assert glossary_file.read_text() == once


#
# add
#
def test_add_takes_an_inline_definition_and_sorts(glossary_file: Path) -> None:
    result = run("add", "Gizmo: A fancy widget.", "-f", str(glossary_file))
    assert result.exit_code == 0, result.output
    assert names(glossary_file) == ["Doohickey", "Gizmo", "Widget"]
    assert term(glossary_file, "Gizmo").definition == "A fancy widget."


def test_add_takes_fields(glossary_file: Path) -> None:
    result = run(
        "add",
        "Gizmo: A fancy widget.",
        "--tag", "core, ui",
        "--tag", "extra",
        "--avoid", "gimmick",
        "--related", "Widget",
        "--code", "`r2.Gizmo`",
        "--field", "pt=engenhoca",
        "-f", str(glossary_file),
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert term(glossary_file, "Gizmo").fields == {
        "tags": "core, ui, extra",
        "avoid": "gimmick",
        "related": "Widget",
        "code": "`r2.Gizmo`",
        "pt": "engenhoca",
    }


def test_add_rejects_a_malformed_field(glossary_file: Path) -> None:
    result = run("add", "Gizmo: g", "--field", "Bad Key=x", "-f", str(glossary_file))
    assert result.exit_code == 2
    assert "Gizmo" not in names(glossary_file)


def test_add_prompts_when_no_definition_is_given(glossary_file: Path) -> None:
    result = run("add", "Gizmo", "-f", str(glossary_file), input="A fancy widget.\n")
    assert result.exit_code == 0, result.output
    assert term(glossary_file, "Gizmo").definition == "A fancy widget."


def test_add_never_prompts_in_agent_mode(glossary_file: Path) -> None:
    result = run("--agent", "add", "Gizmo", "-f", str(glossary_file), input="x\n")
    assert result.exit_code == 1
    assert "inline" in result.output


def test_add_keeps_colons_inside_the_definition(glossary_file: Path) -> None:
    run("add", "Ratio: this: that", "-f", str(glossary_file))
    assert term(glossary_file, "Ratio").definition == "this: that"


def test_add_keeps_the_title_and_the_intro(glossary_file: Path) -> None:
    run("add", "Gizmo: A fancy widget.", "-f", str(glossary_file))
    doc = parse(glossary_file.read_text(encoding="utf-8"))
    assert doc.title == "Glossary of Terms"
    assert doc.intro == "Words used across this project."


def test_add_rejects_a_duplicate_term(glossary_file: Path) -> None:
    result = run("add", "widget: Another one.", "-f", str(glossary_file))
    assert result.exit_code == 1
    assert "already defined" in result.output
    assert glossary_file.read_text() == SAMPLE


def test_add_rejects_an_empty_name(glossary_file: Path) -> None:
    result = run("add", ": A definition.", "-f", str(glossary_file))
    assert result.exit_code == 1
    assert glossary_file.read_text() == SAMPLE


def test_add_rejects_an_empty_prompted_definition(glossary_file: Path) -> None:
    result = run("add", "Gizmo", "-f", str(glossary_file), input="\n")
    assert result.exit_code == 1
    assert glossary_file.read_text() == SAMPLE


def test_add_is_silent_with_qq(glossary_file: Path) -> None:
    result = run("-qq", "add", "Gizmo: g", "-f", str(glossary_file))
    assert (result.exit_code, result.output) == (0, "")


#
# set
#
def test_set_replaces_a_field(glossary_file: Path) -> None:
    result = run("set", "widget", "--avoid", "gizmo", "-f", str(glossary_file))
    assert result.exit_code == 0, result.output
    assert term(glossary_file, "Widget").avoid == ["gizmo"]
    assert term(glossary_file, "Widget").tags == ["core"]


def test_set_changes_the_definition(glossary_file: Path) -> None:
    run("set", "Widget", "--definition", "New text.", "-f", str(glossary_file))
    assert term(glossary_file, "Widget").definition == "New text."


def test_set_unsets_fields(glossary_file: Path) -> None:
    run(
        "set", "Widget", "--unset", "avoid", "--unset", "tags", "-f", str(glossary_file)
    )
    assert term(glossary_file, "Widget").fields == {"related": "Doohickey"}


def test_set_needs_something_to_change(glossary_file: Path) -> None:
    result = run("set", "Widget", "-f", str(glossary_file))
    assert result.exit_code == 2


def test_set_rejects_an_unknown_term(glossary_file: Path) -> None:
    result = run("set", "Nope", "--tag", "x", "-f", str(glossary_file))
    assert result.exit_code == 1
    assert glossary_file.read_text() == SAMPLE


#
# remove
#
def test_remove_deletes_the_term_ignoring_case(glossary_file: Path) -> None:
    result = run("remove", "wIdGeT", "-f", str(glossary_file))
    assert result.exit_code == 0, result.output
    assert names(glossary_file) == ["Doohickey"]


def test_remove_can_empty_the_glossary(glossary_file: Path) -> None:
    run("remove", "Widget", "-f", str(glossary_file))
    run("remove", "Doohickey", "-f", str(glossary_file))
    assert names(glossary_file) == []


def test_remove_rejects_an_unknown_term(glossary_file: Path) -> None:
    result = run("remove", "Nonexistent", "-f", str(glossary_file))
    assert result.exit_code == 1
    assert "No term named" in result.output
    assert glossary_file.read_text() == SAMPLE
