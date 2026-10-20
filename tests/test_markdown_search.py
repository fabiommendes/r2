"""Search in the rendered Markdown pane."""

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Collapsible

from r2.tui.widgets.markdown import DocumentViewer, MarkdownPane
from r2.tui.widgets.search import SearchBar

FILLER = "\n\n".join(f"Paragraph {n} of filler text." for n in range(40))

DOCUMENT = f"""\
# Title

Some **bold needle** and a [link](https://needle.example).

{FILLER}

```python
x = 1
needle = 2
```
"""


class PaneApp(App[None]):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def compose(self) -> ComposeResult:
        yield MarkdownPane()

    async def on_mount(self) -> None:
        await self.query_one(MarkdownPane).open(self.path)


def run(path: Path, test) -> None:  # type: ignore[no-untyped-def]
    async def main() -> None:
        app = PaneApp(path)
        async with app.run_test(size=(60, 20)) as pilot:
            await pilot.pause()
            await app.query_one("FrontmatterMarkdown").rendered()  # type: ignore[attr-defined]
            app.query_one(MarkdownPane)._focus_document()
            await test(app, pilot)

    asyncio.run(main())


def test_searches_the_rendered_text_and_moves_between_matches(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text(DOCUMENT)

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        pane = app.query_one(MarkdownPane)
        viewer = app.query_one(DocumentViewer)
        await pilot.press("slash", *"needle", "enter")
        await pilot.pause()
        assert not app.query_one(SearchBar).display
        # The link target is not shown, so it does not match.
        assert len(pane.matches) == 2
        assert viewer.scroll_offset.y == 0
        document, row, start, end = pane.matches[0]
        assert document.highlights[row][0][:2] == (start, end)
        await pilot.press("down")
        await pilot.pause()
        document, row, _, _ = pane.matches[1]
        assert "needle = 2" in document.plain[row]
        assert viewer.scroll_offset.y > 0
        screen_y = document.content_region.y + row
        assert viewer.content_region.y <= screen_y < viewer.content_region.bottom
        await pilot.press("down")
        assert pane.match_index == 0
        await pilot.press("escape")
        assert pane.matches == []
        assert document.highlights == {}

    run(path, test)


def test_arrows_scroll_without_a_search(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text(DOCUMENT)

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await pilot.press("down", "down")
        assert app.query_one(DocumentViewer).scroll_offset.y == 2

    run(path, test)


def test_opens_the_collapsed_comment_with_the_match(tmp_path: Path) -> None:
    # Five comments, so the first one starts collapsed.
    comments = "".join(
        f"\n---\nby: ana\n\n{'hidden needle' if n == 0 else 'text'}\n" for n in range(5)
    )
    path = tmp_path / "issue.md"
    path.write_text(
        f"---\ntype: issue\nstatus: todo\n---\n\n# An issue\n\nBody.\n{comments}"
    )

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        first = app.query(Collapsible).first()
        assert first.collapsed
        await pilot.press("slash", *"needle", "enter")
        await pilot.pause()
        assert not first.collapsed

    run(path, test)


def test_searches_table_headers_and_cells(tmp_path: Path) -> None:
    path = tmp_path / "table.md"
    path.write_text(
        f"Intro.\n\n{FILLER}\n\n| Name | Needle |\n| --- | --- |\n| a | b |\n"
        "| c | the needle |\n\nAfter needle.\n"
    )

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        pane = app.query_one(MarkdownPane)
        viewer = app.query_one(DocumentViewer)
        await pilot.press("slash", *"needle", "enter")
        await pilot.pause()
        document, header, _, _ = pane.matches[0]
        _, cell, _, _ = pane.matches[1]
        assert "Name" in document.plain[header]
        assert "the needle" in document.plain[cell]
        assert "After needle" in document.plain[pane.matches[2][1]]
        assert viewer.scroll_offset.y > 0
        screen_y = document.content_region.y + header
        assert viewer.content_region.y <= screen_y < viewer.content_region.bottom

    run(path, test)
