"""Search in the rendered Markdown pane."""

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.content import Content
from textual.widgets import Collapsible, MarkdownViewer
from textual.widgets._markdown import MarkdownFence, MarkdownParagraph

from r2.tui.widgets.markdown import MarkdownPane, match_row, shown_text
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
            app.query_one(MarkdownPane)._focus_document()
            await test(app, pilot)

    asyncio.run(main())


def test_match_row_follows_wrapping() -> None:
    content = Content("aaaa bbbb cccc")
    assert match_row(content, 9, 0, wrap=True) == 0
    assert match_row(content, 9, 5, wrap=True) == 0
    assert match_row(content, 9, 10, wrap=True) == 1
    assert match_row(Content("a\nb\nneedle"), 3, 4, wrap=False) == 2


def test_searches_the_rendered_text_and_moves_between_matches(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text(DOCUMENT)

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        pane = app.query_one(MarkdownPane)
        viewer = app.query_one(MarkdownViewer)
        await pilot.press("slash", *"needle", "enter")
        await pilot.pause()
        assert not app.query_one(SearchBar).display
        # The link target is not shown, so it does not match.
        assert len(pane.matches) == 2
        assert viewer.scroll_offset.y == 0
        await pilot.press("down")
        await pilot.pause()
        block = pane.matches[1][0]
        assert isinstance(block, MarkdownFence)
        assert viewer.scroll_offset.y > 0
        assert block.region.overlaps(viewer.content_region)
        await pilot.press("down")
        assert pane.match_index == 0
        await pilot.press("escape")
        assert pane.matches == []
        assert "needle" in block._content.plain
        assert block._content.spans == block._highlighted_code.spans

    run(path, test)


def test_arrows_scroll_without_a_search(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text(DOCUMENT)

    async def test(app: PaneApp, pilot) -> None:  # type: ignore[no-untyped-def]
        await pilot.press("down", "down")
        assert app.query_one(MarkdownViewer).scroll_offset.y == 2

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
        viewer = app.query_one(MarkdownViewer)
        await pilot.press("slash", *"needle", "enter")
        await pilot.pause()
        cells = [w for w, _, _ in pane.matches[:2]]
        assert [w.has_class("header") for w in cells] == [True, False]
        assert isinstance(pane.matches[2][0], MarkdownParagraph)
        assert viewer.scroll_offset.y > 0
        assert cells[0].region.overlaps(viewer.content_region)
        await pilot.press("escape")
        assert all(shown_text(w).spans == [] for w in cells)

    run(path, test)
