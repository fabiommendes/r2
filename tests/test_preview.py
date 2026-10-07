import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Input
from textual.widgets.text_area import Selection

from r2.core.links import Link
from r2.tui.widgets.preview import ExcerptArea, FilePreview, faded_rows, find_matches


def test_fades_both_sides_inside_a_long_file() -> None:
    # Link at lines 20-22 of 100: excerpt 14-28, full context 17-25.
    assert faded_rows(14, 28, 20, 22, 100) == {0, 1, 2, 12, 13, 14}


def test_no_fade_where_the_excerpt_reaches_the_file_edges() -> None:
    # Link at lines 2-3 of 5: the excerpt is the whole file.
    assert faded_rows(1, 5, 2, 3, 5) == set()
    # Near the top only the bottom fades.
    assert faded_rows(1, 10, 4, 4, 50) == {7, 8, 9}


def test_finds_every_occurrence_in_document_order() -> None:
    lines = ["foo bar foo", "", "a foo"]
    assert find_matches(lines, "foo") == [(0, 0, 3), (0, 8, 11), (2, 2, 5)]


def test_lowercase_pattern_ignores_case_but_uppercase_does_not() -> None:
    lines = ["Foo foo FOO"]
    assert find_matches(lines, "foo") == [(0, 0, 3), (0, 4, 7), (0, 8, 11)]
    assert find_matches(lines, "Foo") == [(0, 0, 3)]
    assert find_matches(lines, "") == []


class PreviewApp(App[None]):
    def __init__(self, link: Link) -> None:
        super().__init__()
        self.link = link

    def compose(self) -> ComposeResult:
        yield FilePreview()

    def on_mount(self) -> None:
        self.query_one(FilePreview).show(self.link)
        self.query_one(ExcerptArea).focus()


def test_slash_searches_the_whole_file_and_arrows_move_between_matches(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    lines = [f"line {n}" for n in range(1, 41)]
    lines[1] = lines[34] = "needle here"
    path.write_text("\n".join(lines))

    async def main() -> None:
        # An excerpt around line 20 holds neither match.
        app = PreviewApp(Link(path, 20))
        async with app.run_test() as pilot:
            preview = app.query_one(FilePreview)
            area = app.query_one(ExcerptArea)
            await pilot.press("slash")
            assert app.query_one("#search", Input).has_focus
            await pilot.press(*"needle", "enter")
            assert preview.full
            assert area.has_focus
            assert area.selection == Selection((1, 6), (1, 0))
            await pilot.press("down")
            assert area.selection.end == (34, 0)
            await pilot.press("down")
            assert area.selection.end == (1, 0)
            await pilot.press("up")
            assert area.selection.end == (34, 0)
            await pilot.press("escape")
            assert area.matches == []
            await pilot.press("up")
            assert area.selection.end == (33, 0)

    asyncio.run(main())


def test_escape_closes_the_search_bar_without_searching(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("one\ntwo\n")

    async def main() -> None:
        app = PreviewApp(Link(path))
        async with app.run_test() as pilot:
            await pilot.press("slash", "t", "escape")
            assert not app.query_one("#search", Input).display
            assert app.query_one(ExcerptArea).has_focus
            assert app.query_one(ExcerptArea).matches == []

    asyncio.run(main())


def test_ctrl_shift_c_copies_the_selection(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("one\ntwo\n")

    async def main() -> None:
        app = PreviewApp(Link(path, 2))
        async with app.run_test() as pilot:
            await pilot.press("ctrl+shift+c")
            assert app.clipboard == "two"

    asyncio.run(main())
