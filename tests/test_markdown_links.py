"""Links in the Markdown documents of the TUI views."""

from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import TabbedContent

from r2.core.links import Link
from r2.tui.app import R2App
from r2.tui.views.project import ProjectView
from r2.tui.widgets.markdown import DocumentViewer, FrontmatterMarkdown, MarkdownBrowser
from tests.test_tui_views import drive


def test_clicking_a_local_link_opens_its_file(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("[the other doc](other.md)\n")
    (docs / "other.md").write_text("# Other\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "docs"
        await pilot.pause()
        browser = app.query_one("#docs MarkdownBrowser", MarkdownBrowser)
        await browser.open(docs / "guide.md")
        await pilot.pause()
        document = browser.query_one(FrontmatterMarkdown)
        await pilot.click(document, offset=(4, 0))
        await pilot.pause()
        await pilot.pause()
        assert browser.query_one(DocumentViewer).location == docs / "other.md"
        assert document.plain[0].startswith("OTHER")

    drive(test, monkeypatch)


def test_clicking_a_code_span_that_names_a_file_shows_it(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".git").mkdir()
    source = tmp_path / "r2" / "core" / "links.py"
    source.parent.mkdir(parents=True)
    source.write_text("LINKS = 1\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("`r2/core/links.py` and `not/a/file.py`\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "docs"
        await pilot.pause()
        browser = app.query_one("#docs MarkdownBrowser", MarkdownBrowser)
        await browser.open(docs / "guide.md")
        await pilot.pause()
        document = browser.query_one(FrontmatterMarkdown)
        # The second span names no file, so a click on it does nothing.
        await pilot.click(document, offset=(24, 0))
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "docs"
        await pilot.click(document, offset=(4, 0))
        await pilot.pause()
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "project"
        assert app.query_one(ProjectView).current_link() == Link(source.resolve())

    drive(test, monkeypatch)
