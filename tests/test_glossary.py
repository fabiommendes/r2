"""
Unit tests for r2.core.glossary.

Everything here goes through the module's public API -- `parse`, `Glossary`
and `Term`, i.e. exactly what `r2.core.glossary.__all__` exports. The parser
itself is an implementation detail and is only exercised through the
documents `parse` is given, so the suite stays valid if the parsing strategy
is rewritten.

The document shape under test is the one fixed by the module docstring:

    # Glossary [optional subtitle]

    One or more paragraphs of introduction.

    ---

    ## Term

    The definition.

Unlike tests/test_pyproject_tasks.py these are pure unit tests: no
subprocesses, no temporary directories, nothing on disk.
"""

from __future__ import annotations

import pytest

from r2.core.glossary import Glossary, Term, parse

SAMPLE = """
# Glossary

The words below mean exactly what this document says they mean.

Nothing more, nothing less.

---

## Alpha

The first letter.

## beta

The second letter,
spread over two lines.
"""

SAMPLE_INTRO = (
    "The words below mean exactly what this document says they mean.\n"
    "\n"
    "Nothing more, nothing less."
)


@pytest.fixture
def glossary() -> Glossary:
    return parse(SAMPLE)


#
# Term
#
def test_term_holds_a_name_and_a_definition() -> None:
    term = Term(name="Alpha", definition="The first letter.")
    assert term.name == "Alpha"
    assert term.definition == "The first letter."
    assert term == Term("Alpha", "The first letter.")


#
# Glossary
#
def test_title_defaults_to_glossary() -> None:
    assert Glossary(terms=[], intro="").title == "Glossary"


def test_sorted_orders_terms_case_insensitively() -> None:
    doc = Glossary(
        terms=[Term("beta", "b"), Term("Alpha", "a"), Term("Gamma", "g")],
        intro="intro",
    )
    assert [term.name for term in doc.sorted().terms] == ["Alpha", "beta", "Gamma"]


def test_sorted_does_not_mutate_the_original() -> None:
    terms = [Term("beta", "b"), Term("Alpha", "a")]
    doc = Glossary(terms=terms, intro="intro")

    doc.sorted()

    assert [term.name for term in doc.terms] == ["beta", "Alpha"]
    assert doc.terms is terms


def test_sorted_keeps_the_intro_and_the_title() -> None:
    doc = Glossary(terms=[], intro="intro", title="Glossary of Terms")
    result = doc.sorted()
    assert result.intro == "intro"
    assert result.title == "Glossary of Terms"


def test_render_writes_the_intro_then_a_blank_line_then_the_terms() -> None:
    doc = Glossary(
        terms=[Term("Alpha", "The first letter."), Term("beta", "The second one.")],
        intro="An intro.",
    )
    assert doc.render() == (
        "An intro.\n\nAlpha: The first letter.\nbeta: The second one."
    )


def test_render_of_an_empty_glossary_is_just_the_intro() -> None:
    assert Glossary(terms=[], intro="An intro.").render() == "An intro.\n"


#
# parse: the title
#
def test_parse_reads_the_title(glossary: Glossary) -> None:
    assert glossary.title == "Glossary"


def test_parse_keeps_the_optional_subtitle() -> None:
    assert parse("# Glossary of Terms\n\n---\n").title == "Glossary of Terms"


def test_parse_accepts_a_title_in_any_case() -> None:
    assert parse("# GLOSSARY\n\n---\n").title == "GLOSSARY"


def test_parse_skips_blank_lines_before_the_title() -> None:
    assert parse("\n\n\n# Glossary\n\n---\n").title == "Glossary"


#
# parse: the intro
#
def test_parse_reads_the_intro(glossary: Glossary) -> None:
    assert glossary.intro == SAMPLE_INTRO


def test_parse_accepts_a_document_with_no_intro() -> None:
    doc = parse("# Glossary\n\n---\n\n## Alpha\n\nThe first letter.\n")
    assert doc.intro == ""
    assert doc.terms == [Term("Alpha", "The first letter.")]


def test_parse_of_an_intro_only_document_has_no_terms() -> None:
    doc = parse("# Glossary\n\nJust an intro.\n\n---\n")
    assert doc.intro == "Just an intro."
    assert doc.terms == []


#
# parse: the terms
#
def test_parse_reads_the_terms_in_document_order(glossary: Glossary) -> None:
    assert [term.name for term in glossary.terms] == ["Alpha", "beta"]


def test_parse_reads_a_single_line_definition(glossary: Glossary) -> None:
    assert glossary.terms[0].definition == "The first letter."


def test_parse_keeps_the_line_breaks_of_a_multi_line_definition(
    glossary: Glossary,
) -> None:
    assert glossary.terms[1].definition == "The second letter,\nspread over two lines."


def test_parse_keeps_the_blank_line_inside_a_multi_paragraph_definition() -> None:
    doc = parse(
        "# Glossary\n\n---\n\n## Alpha\n\nFirst paragraph.\n\nSecond paragraph.\n"
    )
    assert doc.terms == [Term("Alpha", "First paragraph.\n\nSecond paragraph.")]


def test_parse_tolerates_extra_blank_lines_between_terms() -> None:
    doc = parse("# Glossary\n\n---\n\n## Alpha\n\na\n\n\n\n## Beta\n\nb\n")
    assert doc.terms == [Term("Alpha", "a"), Term("Beta", "b")]


def test_parse_tolerates_trailing_blank_lines() -> None:
    doc = parse(SAMPLE + "\n\n\n")
    assert [term.name for term in doc.terms] == ["Alpha", "beta"]


def test_parse_accepts_a_term_with_an_empty_definition() -> None:
    doc = parse("# Glossary\n\n---\n\n## Alpha\n\n## Beta\n\nb\n")
    assert doc.terms == [Term("Alpha", ""), Term("Beta", "b")]


#
# parse: rejected documents
#
def test_parse_rejects_an_empty_document() -> None:
    with pytest.raises(ValueError):
        parse("")


def test_parse_rejects_a_document_without_a_heading() -> None:
    with pytest.raises(ValueError):
        parse("Glossary\n\n---\n")


def test_parse_rejects_a_heading_that_is_not_a_glossary() -> None:
    with pytest.raises(ValueError):
        parse("# Notes\n\nintro\n\n---\n\n## Alpha\n\na\n")


def test_parse_rejects_a_deeper_heading() -> None:
    with pytest.raises(ValueError):
        parse("## Glossary\n\n---\n")


def test_parse_rejects_a_term_that_is_not_a_heading() -> None:
    with pytest.raises(ValueError):
        parse("# Glossary\n\n---\n\nAlpha\n\nThe first letter.\n")


#
# parse composed with the rest of the public API
#
def test_a_parsed_glossary_can_be_sorted_and_rendered(glossary: Glossary) -> None:
    rendered = glossary.sorted().render()
    assert rendered.startswith(SAMPLE_INTRO)
    assert "Alpha: The first letter." in rendered
    assert rendered.index("Alpha:") < rendered.index("beta:")


def test_sorting_a_parsed_glossary_keeps_its_title() -> None:
    doc = parse("# Glossary of Terms\n\n---\n\n## Beta\n\nb\n\n## Alpha\n\na\n")
    assert doc.sorted().title == "Glossary of Terms"


#
# to_markdown
#
def test_to_markdown_round_trips_through_parse(glossary: Glossary) -> None:
    assert parse(glossary.to_markdown()) == glossary


def test_to_markdown_round_trips_a_glossary_with_a_subtitle() -> None:
    doc = Glossary(terms=[Term("Alpha", "a")], intro="i", title="Glossary of Terms")
    assert parse(doc.to_markdown()) == doc


def test_to_markdown_round_trips_an_empty_glossary() -> None:
    doc = Glossary(terms=[], intro="")
    assert parse(doc.to_markdown()) == doc


def test_to_markdown_round_trips_a_multi_paragraph_definition() -> None:
    doc = Glossary(terms=[Term("Alpha", "First.\n\nSecond.")], intro="")
    assert parse(doc.to_markdown()) == doc


def test_to_markdown_writes_markdown_headings() -> None:
    doc = Glossary(terms=[Term("Alpha", "a")], intro="An intro.")
    assert doc.to_markdown() == ("# Glossary\n\nAn intro.\n\n---\n\n## Alpha\n\na\n")


def test_to_markdown_is_idempotent(glossary: Glossary) -> None:
    once = glossary.to_markdown()
    assert parse(once).to_markdown() == once
