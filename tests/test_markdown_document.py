"""The Markdown document rendered by rows."""

import asyncio
from pathlib import Path

from rich.theme import Theme
from textual.app import App, ComposeResult

from r2.tui.widgets.document import (
    FIRST_ROWS,
    Look,
    MarkdownDocument,
    Rendered,
    parse,
    render_blocks,
    slugs,
)
from r2.tui.widgets.markdown import DocumentViewer, FrontmatterMarkdown, MarkdownPane

FILLER = "\n\n".join(f"Paragraph {n} of filler text." for n in range(40))


class PaneApp(App[None]):
    def compose(self) -> ComposeResult:
        yield MarkdownPane()


def run(test, size: tuple[int, int] = (60, 20)) -> None:  # type: ignore[no-untyped-def]
    async def main() -> None:
        app = PaneApp()
        async with app.run_test(size=size) as pilot:
            await test(app, pilot)

    asyncio.run(main())


def test_anchors_follow_github_slugs() -> None:
    blocks = parse("# Intro\n\ntext\n\n## Two words!\n\n# Intro\n")
    assert slugs(blocks) == {"intro": 0, "two-words": 2, "intro-1": 3}


def rendered_rows(markdown: str, width: int = 40) -> list[str]:
    rendered = Rendered(width, Look(Theme({}), "monokai", "#000000"))
    render_blocks(rendered, parse(markdown))
    return [row.rstrip() for row in rendered.plain]


def test_code_has_one_blank_row_above_and_below() -> None:
    rows = rendered_rows("Text\n\n```python\nx = 1\n```\n\nAfter\n")
    assert rows == ["Text", "", "", " x = 1", "", "", "After"]


def test_tables_draw_a_grid_and_align_columns() -> None:
    rows = rendered_rows(
        "Text\n\n| Name | Value |\n| --- | ---: |\n| alpha | 1 |\n| beta | 22 |\n"
    )
    assert rows == [
        "Text",
        "",
        "╭───────┬───────╮",
        "│ Name  │ Value │",
        "├───────┼───────┤",
        "│ alpha │     1 │",
        "├───────┼───────┤",
        "│ beta  │    22 │",
        "╰───────┴───────╯",
    ]


def test_a_long_document_renders_the_rest_in_the_background(tmp_path: Path) -> None:
    path = tmp_path / "long.md"
    path.write_text("\n\n".join([FILLER] * 5))

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await app.query_one(MarkdownPane).open(path)
        await pilot.pause()
        document = app.query_one(FrontmatterMarkdown)
        await document.rendered()
        assert len(document.plain) > FIRST_ROWS
        assert document.plain[-1].startswith("Paragraph 39")

    run(test)


def test_a_local_link_opens_its_file_at_the_anchor(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    other = tmp_path / "docs" / "other.md"
    other.write_text(f"# Other\n\n{FILLER}\n\n## Far away\n\n{FILLER}\n")
    path = tmp_path / "doc.md"
    path.write_text("[go](docs/other.md#far-away)\n")

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await app.query_one(MarkdownPane).open(path)
        await pilot.pause()
        document = app.query_one(FrontmatterMarkdown)
        document.post_message(
            MarkdownDocument.LinkClicked(document, "docs/other.md#far-away")
        )
        await pilot.pause()
        await pilot.pause()
        viewer = app.query_one(DocumentViewer)
        assert viewer.location == other
        row = document.row_of("far-away")
        assert row is not None
        assert viewer.scroll_offset.y == row

    run(test)


def test_an_unreadable_file_shows_why(tmp_path: Path) -> None:
    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await app.query_one(MarkdownPane).open(tmp_path / "gone.md")
        await pilot.pause()
        document = app.query_one(FrontmatterMarkdown)
        await document.rendered()
        assert "Cannot read" in " ".join(document.plain)

    run(test)


def test_search_follows_the_rows_after_a_resize(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    words = " ".join(f"word{n}" for n in range(60))
    path.write_text(f"{words} needle\n")

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        pane = app.query_one(MarkdownPane)
        await pane.open(path)
        await pilot.pause()
        await app.query_one(FrontmatterMarkdown).rendered()
        pane.search("needle")
        document, row, _, _ = pane.matches[0]
        await pilot.resize_terminal(120, 20)
        await pilot.pause()
        await document.rendered()
        await pilot.pause()
        _, moved, start, _ = pane.matches[0]
        assert moved < row
        assert document.plain[moved][start:].startswith("needle")

    run(test)
