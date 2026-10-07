"""
Tests for r2's own views running in the real app under Textual's pilot.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import TabbedContent

from r2.tui.app import R2App
from r2.tui.widgets.markdown import MarkdownBrowser
from r2.tui.widgets.status_menu import StatusMenu


def drive(
    test: Callable[[R2App, Pilot[None]], Awaitable[None]],
    monkeypatch: pytest.MonkeyPatch,
) -> list[list[str]]:
    """Run test in the app and return the commands it handed the terminal to."""
    commands: list[list[str]] = []
    monkeypatch.setattr(
        R2App,
        "_hand_over",
        lambda self, command, cwd=None, banner="": commands.append(command),
    )
    app = R2App()

    async def main() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            await test(app, pilot)

    asyncio.run(main())
    return commands


def footer_keys(app: R2App) -> set[str]:
    return {active.binding.key for active in app.active_bindings.values()}


def test_excerpt_toggle_belongs_to_the_live_view(
    config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "live"
        await pilot.pause()
        assert "f" in footer_keys(app)
        app.query_one(TabbedContent).active = "docs"
        await pilot.pause()
        assert "f" not in footer_keys(app)

    drive(test, monkeypatch)


def test_edit_opens_the_document_of_the_docs_view(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("R2_EDITOR", "my-editor")
    doc = tmp_path / "docs" / "guide.md"
    doc.parent.mkdir()
    doc.write_text("# Guide\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "docs"
        await pilot.pause()
        await app.query_one("#docs MarkdownBrowser", MarkdownBrowser).open(doc)
        await pilot.press("e")

    assert drive(test, monkeypatch) == [["my-editor", str(doc)]]


def test_clicking_the_status_pill_opens_the_status_menu(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issue = tmp_path / "dev" / "issues" / "bug.md"
    issue.parent.mkdir(parents=True)
    issue.write_text("---\ntype: issue\nstatus: todo\n---\n\n# Bug\n\nIt breaks.\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "issues"
        await pilot.pause()
        await app.query_one("#issues MarkdownBrowser", MarkdownBrowser).open(issue)
        await pilot.pause()
        # Padding, then "status" padded to the "status" key width, then the pill.
        await pilot.click("#issues MetaBar", offset=(10, 1))
        await pilot.pause()
        assert isinstance(app.screen, StatusMenu)

    drive(test, monkeypatch)
