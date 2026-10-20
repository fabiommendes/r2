"""
Tests for r2's own views running in the real app under Textual's pilot.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from textual import events
from textual.pilot import Pilot
from textual.widgets import Button, Input, Label, RichLog, TabbedContent, Tree

from r2.core.adrs import load as load_adr
from r2.core.glossary import parse as parse_glossary
from r2.core.issues import Issue, load
from r2.core.rfcs import load as load_rfc
from r2.tui.app import R2App
from r2.tui.views.glossary import GlossaryView
from r2.tui.widgets.command_box import CommandBox, CommandRun
from r2.tui.widgets.issue_form import Cycle, IssueForm
from r2.tui.widgets.markdown import FrontmatterMarkdown, MarkdownBrowser
from r2.tui.widgets.prompts import Ask, Confirm
from r2.tui.widgets.status_menu import Pick, StatusMenu


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


def test_clicking_a_related_issue_opens_it(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issues = tmp_path / "dev" / "issues"
    issues.mkdir(parents=True)
    (issues / "old.md").write_text("---\ntype: issue\nstatus: todo\n---\n\n# Old\n")
    issue = issues / "new.md"
    issue.write_text("---\ntype: issue\nstatus: todo\nrelatedTo: [old]\n---\n\n# New\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "issues"
        await pilot.pause()
        browser = app.query_one("#issues MarkdownBrowser", MarkdownBrowser)
        await browser.open(issue)
        await pilot.pause()
        # Padding, then the "relatedTo" key column, on the third line.
        await pilot.click("#issues MetaBar", offset=(13, 2))
        await pilot.pause()
        assert browser.current == issues / "old.md"
        cursor = browser.query_one(Tree).cursor_node
        assert cursor is not None and cursor.data == issues / "old.md"

    drive(test, monkeypatch)


def test_a_related_spec_opens_in_the_docs_view(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec = tmp_path / "dev" / "spec" / "format.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Format\n")
    issue = tmp_path / "dev" / "issues" / "new.md"
    issue.parent.mkdir(parents=True)
    issue.write_text(
        "---\ntype: issue\nstatus: todo\nrelatedTo: [dev/spec/format.md]\n---\n"
    )

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "issues"
        await pilot.pause()
        await app.query_one("#issues MarkdownBrowser", MarkdownBrowser).open(issue)
        await pilot.pause()
        await pilot.click("#issues MetaBar", offset=(13, 2))
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "docs"
        docs = app.query_one("#docs MarkdownBrowser", MarkdownBrowser)
        assert docs.current == spec
        cursor = docs.query_one(Tree).cursor_node
        assert cursor is not None and cursor.data == spec

    drive(test, monkeypatch)


def test_issue_form_steps_through_values_with_the_arrows(
    config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def test(app: R2App, pilot: Pilot[None]) -> None:
        form = IssueForm()
        await app.push_screen(form)
        await pilot.pause()
        kind = form.query_one("#kind", Cycle)
        priority = form.query_one("#priority", Cycle)
        assert kind.value is None
        kind.focus()
        await pilot.press("right")
        assert kind.value == "defect"
        await pilot.press("left", "left")
        assert kind.value == "task"
        priority.focus()
        await pilot.press("right")
        assert priority.value == "high"

    drive(test, monkeypatch)


def test_issue_form_moves_with_up_down_and_creates_on_enter(
    config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[Issue | None] = []

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        form = IssueForm()
        await app.push_screen(form, created.append)
        await pilot.pause()
        form.query_one("#title", Input).focus()
        await pilot.press(*"Crash", "down", "down")
        assert form.focused is form.query_one("#priority", Cycle)
        await pilot.press("right", "up", "up", "down")
        assert form.focused is form.query_one("#kind", Cycle)
        await pilot.press("enter")
        await pilot.pause()

    drive(test, monkeypatch)
    [issue] = created
    assert issue is not None
    assert issue.title == "Crash"
    assert issue.meta["priority"] == "high"


def test_run_command_shows_the_output_of_a_command_run_in_the_project(
    config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SHELL", "/bin/sh")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await pilot.press("dollar_sign")
        await pilot.pause()
        box = app.screen
        assert isinstance(box, CommandBox)
        await pilot.press(*"pwd; echo hi; false", "enter")
        assert box._run is not None
        await box._run.wait()
        await pilot.pause()
        run = box.query_one(CommandRun)
        lines = [strip.text for strip in run.query_one(RichLog).lines]
        assert lines == [str(tmp_path), "hi"]
        assert str(run.query_one("#status", Label).content) == "exit 1"
        await pilot.press("ctrl+l")
        await pilot.pause()
        assert not box.query(CommandRun)
        await pilot.press("escape")
        assert not isinstance(app.screen, CommandBox)

    drive(test, monkeypatch)


def test_clearing_a_running_command_kills_it(
    config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SHELL", "/bin/sh")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await pilot.press("dollar_sign")
        await pilot.pause()
        box = app.screen
        assert isinstance(box, CommandBox)
        await pilot.press(*"sleep 30", "enter")
        await pilot.pause(0.2)
        process = box._process
        assert process is not None
        await pilot.click("#clear")
        assert await asyncio.wait_for(process.wait(), 5) != 0
        await pilot.pause()
        assert not box.query(CommandRun)
        assert box.focused is box.query_one("#command", Input)

    drive(test, monkeypatch)


def issue_on_display(
    tmp_path: Path, status: str = "todo", tags: str = ""
) -> tuple[Path, Callable[[R2App, Pilot[None]], Awaitable[MarkdownBrowser]]]:
    """An issue file and a coroutine that shows it in the Issues view."""
    issue = tmp_path / "dev" / "issues" / "bug.md"
    issue.parent.mkdir(parents=True)
    extra = f"tags: [{tags}]\n" if tags else ""
    issue.write_text(f"---\ntype: issue\nstatus: {status}\n{extra}---\n\n# Bug\n")

    async def show(app: R2App, pilot: Pilot[None]) -> MarkdownBrowser:
        app.query_one(TabbedContent).active = "issues"
        await pilot.pause()
        browser = app.query_one("#issues MarkdownBrowser", MarkdownBrowser)
        await browser.open(issue)
        await pilot.pause()
        return browser

    return issue, show


def button(app: R2App, command: str) -> Button:
    return app.query_one(f"#issues CommandBar #command-{command}", Button)


def test_advance_moves_the_issue_to_its_next_status(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issue, show = issue_on_display(tmp_path, "in_progress")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot)
        assert str(button(app, "advance").label) == "in review →"
        button(app, "advance").press()
        await pilot.pause(0.2)
        assert load(issue).status == "in_review"
        assert str(button(app, "advance").label) == "completed →"

    drive(test, monkeypatch)


def test_the_tree_shows_the_progress_of_the_plan(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issue, show = issue_on_display(tmp_path)
    issue.write_text(issue.read_text() + "\n## Plan\n\n- [x] One.\n- [ ] Two.\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        browser = await show(app, pilot)
        [group] = browser.query_one(Tree).root.children
        assert [str(leaf.label) for leaf in group.children] == ["Bug 1/2"]

    drive(test, monkeypatch)


def test_tags_replaces_the_tags_of_the_issue(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issue, show = issue_on_display(tmp_path, tags="ui")
    other = issue.with_name("other.md")
    other.write_text("---\ntype: issue\nstatus: todo\ntags: [tui, ui]\n---\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot)
        button(app, "tags").press()
        await pilot.pause()
        box = app.screen
        assert isinstance(box, Ask)
        assert box.query_one(Input).value == "ui"
        choices = [str(b.label) for b in box.query("#choices Button").results(Button)]
        assert choices == ["ui", "tui"]
        await pilot.click("#choices Button:last-of-type")
        await pilot.press(*", cli", "enter")
        await pilot.pause()
        assert load(issue).meta["tags"] == ["ui", "tui", "cli"]

    drive(test, monkeypatch)


def test_delete_removes_the_issue_after_confirming(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issue, show = issue_on_display(tmp_path)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        browser = await show(app, pilot)
        button(app, "delete").press()
        await pilot.pause()
        assert isinstance(app.screen, Confirm)
        await pilot.press("escape")
        await pilot.pause()
        assert issue.exists()
        button(app, "delete").press()
        await pilot.pause()
        await pilot.click("#yes")
        await pilot.pause(0.2)
        assert not issue.exists()
        assert browser.current is None
        assert not app.query_one("#issues CommandBar").display

    drive(test, monkeypatch)


def test_entering_the_issue_focuses_the_document_not_the_commands(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, show = issue_on_display(tmp_path)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot)
        app.query_one("#issues Tree").focus()
        await pilot.press("right")
        await pilot.pause()
        assert isinstance(app.focused, FrontmatterMarkdown)

    drive(test, monkeypatch)


def test_a_doc_deleted_behind_the_tree_shows_why_it_cannot_be_read(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc = tmp_path / "docs" / "guide.md"
    doc.parent.mkdir()
    doc.write_text("# Guide\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "docs"
        await pilot.pause()
        doc.unlink()
        select_doc(app, "docs", doc)
        await pilot.pause()
        document = app.query_one("#docs FrontmatterMarkdown", FrontmatterMarkdown)
        assert "Cannot read" in "\n".join(document.render_at(80))

    drive(test, monkeypatch)


def select_doc(app: R2App, view: str, path: Path) -> None:
    """Select the tree leaf of path, as Enter does."""
    tree = app.query_one(f"#{view} Tree", Tree)
    nodes = list(tree.root.children)
    while nodes:
        node = nodes.pop(0)
        if node.data == path:
            tree.select_node(node)
            return
        nodes.extend(node.children)
    raise AssertionError(f"{path} is not in the {view} tree")


def history_setup(tmp_path: Path) -> tuple[Path, Path]:
    """A doc and an issue, with the Issues view not yet loaded."""
    doc = tmp_path / "docs" / "guide.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Guide\n")
    issue, _ = issue_on_display(tmp_path)
    return doc, issue


async def open_doc_then_issues(app: R2App, pilot: Pilot[None], doc: Path) -> None:
    tabs = app.query_one(TabbedContent)
    tabs.active = "docs"
    await pilot.pause()
    select_doc(app, "docs", doc)
    await pilot.pause()
    tabs.active = "issues"
    await pilot.pause()


def test_back_returns_to_the_doc_and_forward_to_the_issues(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc, _ = history_setup(tmp_path)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await open_doc_then_issues(app, pilot, doc)
        await app.action_back()
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "docs"
        browser = app.query_one("#docs MarkdownBrowser", MarkdownBrowser)
        assert browser.current == doc
        tree = app.query_one("#docs Tree", Tree)
        assert tree.cursor_node is not None and tree.cursor_node.data == doc
        await app.action_forward()
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "issues"

    drive(test, monkeypatch)


def test_a_visit_after_going_back_clears_forward(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc, _ = history_setup(tmp_path)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await open_doc_then_issues(app, pilot, doc)
        await app.action_back()
        await pilot.pause()
        assert app.query_one("#forward").has_class("-unavailable") is False
        app.query_one(TabbedContent).active = "live"
        await pilot.pause()
        assert app.query_one("#forward").has_class("-unavailable")
        await app.action_forward()
        assert app.query_one(TabbedContent).active == "live"

    drive(test, monkeypatch)


def test_the_arrows_dim_when_unavailable_and_click_when_not(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc, _ = history_setup(tmp_path)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        back, forward = app.query_one("#back"), app.query_one("#forward")
        assert back.has_class("-unavailable") and forward.has_class("-unavailable")
        await open_doc_then_issues(app, pilot, doc)
        assert not back.has_class("-unavailable")
        assert forward.has_class("-unavailable")
        await pilot.click("#back")
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "docs"
        assert not forward.has_class("-unavailable")

    drive(test, monkeypatch)


def test_the_cursor_moving_is_not_a_visit(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doc, _ = history_setup(tmp_path)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        tabs = app.query_one(TabbedContent)
        first = tabs.active
        tabs.active = "docs"
        await pilot.pause()
        tree = app.query_one("#docs Tree", Tree)
        leaf = next(n for section in tree.root.children for n in section.children)
        tree.move_cursor(leaf)
        await pilot.pause()
        await app.action_back()
        await pilot.pause()
        assert tabs.active == first
        assert app.query_one("#back").has_class("-unavailable")

    drive(test, monkeypatch)


def adr_file(folder: Path, stem: str, status: str, extra: str = "") -> Path:
    path = folder / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    title = stem.partition("-")[2].replace("-", " ").capitalize()
    path.write_text(f"---\ntype: adr\nstatus: {status}\n{extra}---\n\n# {title}\n")
    return path


async def show_adr(app: R2App, pilot: Pilot[None], path: Path) -> MarkdownBrowser:
    app.query_one(TabbedContent).active = "adrs"
    await pilot.pause()
    browser = app.query_one("#adrs MarkdownBrowser", MarkdownBrowser)
    await browser.open(path)
    await pilot.pause()
    return browser


def adr_button(app: R2App, command: str) -> Button:
    return app.query_one(f"#adrs CommandBar #command-{command}", Button)


def test_new_adr_takes_the_next_number_and_opens_the_editor(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("R2_EDITOR", "my-editor")
    folder = tmp_path / "dev" / "adr"
    adr_file(folder, "0004-old", "accepted")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "adrs"
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, Ask)
        await pilot.press(*"Use TOML", "enter")
        await pilot.pause()

    commands = drive(test, monkeypatch)
    created = folder / "0005-use-toml.md"
    adr = load_adr(created)
    assert (adr.title, adr.status) == ("Use TOML", "proposed")
    assert commands[-1][-1] == str(created)


def test_advance_cycles_an_adr_between_proposed_accepted_and_rejected(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = adr_file(tmp_path / "dev" / "adr", "0001-use-toml", "proposed")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show_adr(app, pilot, path)
        assert str(adr_button(app, "advance").label) == "accepted →"
        adr_button(app, "advance").press()
        await pilot.pause(0.2)
        assert load_adr(path).status == "accepted"
        assert "decided" in load_adr(path).meta
        assert str(adr_button(app, "advance").label) == "rejected →"

    drive(test, monkeypatch)


def test_supersedes_records_the_replacement_on_both_adrs(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "dev" / "adr"
    old = adr_file(folder, "0001-json-config", "accepted")
    new = adr_file(folder, "0002-toml-config", "accepted")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show_adr(app, pilot, new)
        adr_button(app, "supersede").press()
        await pilot.pause()
        assert isinstance(app.screen, Pick)
        await pilot.press("enter")
        await pilot.pause(0.2)

    drive(test, monkeypatch)
    assert load_adr(new).meta["supersedes"] == ["0001-json-config"]
    assert load_adr(old).status == "superseded"
    assert load_adr(old).meta["supersededBy"] == "0002-toml-config"


def test_the_tree_trusts_supersedes_over_the_old_adr_status(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "dev" / "adr"
    old = adr_file(folder, "0001-json-config", "accepted")
    new = adr_file(folder, "0002-toml", "accepted", "supersedes: [0001-json-config]\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        browser = await show_adr(app, pilot, new)
        groups = {
            str(node.label).split()[0]: [leaf.data for leaf in node.children]
            for node in browser.query_one(Tree).root.children
        }
        assert groups == {"accepted": [new], "superseded": [old]}

    drive(test, monkeypatch)


def test_clicking_a_superseded_adr_opens_it(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "dev" / "adr"
    old = adr_file(folder, "0001-json-config", "superseded")
    new = adr_file(folder, "0002-toml", "accepted", "supersedes: [0001-json-config]\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        browser = await show_adr(app, pilot, new)
        # Padding, then the "supersedes" key column, on the third line.
        await pilot.click("#adrs MetaBar", offset=(14, 2))
        await pilot.pause()
        assert browser.current == old

    drive(test, monkeypatch)


def test_a_gui_editor_starts_detached_and_reloads_on_coming_back(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("R2_EDITOR", "code -w")
    launched: list[list[str]] = []
    monkeypatch.setattr("r2.tui.app.launch_detached", launched.append)
    doc = tmp_path / "docs" / "guide.md"
    doc.parent.mkdir()
    doc.write_text("# Guide\n")
    reloads: list[str] = []

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "docs"
        await pilot.pause()
        await app.query_one("#docs MarkdownBrowser", MarkdownBrowser).open(doc)
        view = app._active_view()
        monkeypatch.setattr(view, "reload", lambda: reloads.append("reload"))
        await pilot.press("e")
        await pilot.pause()
        assert reloads == []
        app.post_message(events.AppFocus())
        await pilot.pause()
        app.post_message(events.AppFocus())
        await pilot.pause()

    assert drive(test, monkeypatch) == []
    assert launched == [["code", str(doc)]]
    assert reloads == ["reload"]


def test_empty_comments_are_not_shown(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issue, show = issue_on_display(tmp_path)
    text = issue.read_text()
    issue.write_text(text + "\n---\nby: fabio\n\nKept.\n\n---\nby: fabio\n\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot)
        await pilot.pause()
        assert len(app.query("#issues CommentThread Collapsible")) == 1

    drive(test, monkeypatch)


GLOSSARY = """\
# Glossary

Words of this project.

---

## Comment

A reply in a thread.

- tags: process

## Issue

A unit of work.

- tags: process, files
- avoid: ticket
- related: Comment, Nothing

## Loose

No tags.
"""


async def show_glossary(app: R2App, pilot: Pilot[None]) -> GlossaryView:
    app.query_one(TabbedContent).active = "glossary"
    await pilot.pause()
    return app.query_one(GlossaryView)


def tree_groups(view: GlossaryView) -> dict[str, list[str]]:
    return {
        str(node.label).split()[0]: [str(leaf.label) for leaf in node.children]
        for node in view.query_one(Tree).root.children
    }


def test_glossary_groups_terms_by_tag_and_filters_by_avoided_words(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "GLOSSARY.md").write_text(GLOSSARY)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        view = await show_glossary(app, pilot)
        assert tree_groups(view) == {
            "files": ["Issue"],
            "process": ["Comment", "Issue"],
            "untagged": ["Loose"],
        }
        view.query_one("#filter", Input).value = "ticket"
        await pilot.pause()
        assert tree_groups(view) == {"files": ["Issue"], "process": ["Issue"]}

    drive(test, monkeypatch)


def test_clicking_a_related_term_shows_it_and_edit_opens_its_line(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("R2_EDITOR", "my-editor")
    path = tmp_path / "GLOSSARY.md"
    path.write_text(GLOSSARY)

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        view = await show_glossary(app, pilot)
        view.select("Issue")
        await pilot.pause()
        # Padding, then the "related" key column, on the third line.
        await pilot.click("#glossary MetaBar", offset=(12, 2))
        await pilot.pause()
        assert view.current is not None and view.current.name == "Comment"
        await pilot.press("e")

    assert drive(test, monkeypatch) == [["my-editor", "+7", str(path)]]


def test_new_term_is_added_sorted_and_opened_in_the_editor(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("R2_EDITOR", "my-editor")
    path = tmp_path / "GLOSSARY.md"

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        view = await show_glossary(app, pilot)
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, Ask)
        await pilot.press(*"Thread", "enter")
        await pilot.pause()
        assert view.current is not None and view.current.name == "Thread"

    commands = drive(test, monkeypatch)
    assert [t.name for t in parse_glossary(path.read_text()).terms] == ["Thread"]
    assert commands == [["my-editor", "+12", str(path)]]


def rfc_file(folder: Path, slug: str, status: str, extra: str = "") -> Path:
    path = folder / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    title = slug.replace("-", " ").capitalize()
    path.write_text(f"---\ntype: rfc\nstatus: {status}\n{extra}---\n\n# {title}\n")
    return path


async def show_rfc(app: R2App, pilot: Pilot[None], path: Path) -> MarkdownBrowser:
    app.query_one(TabbedContent).active = "rfcs"
    await pilot.pause()
    browser = app.query_one("#rfcs MarkdownBrowser", MarkdownBrowser)
    await browser.open(path)
    await pilot.pause()
    return browser


def rfc_button(app: R2App, command: str) -> Button:
    return app.query_one(f"#rfcs CommandBar #command-{command}", Button)


def test_new_rfc_takes_a_slug_and_opens_the_editor(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("R2_EDITOR", "my-editor")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "rfcs"
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, Ask)
        await pilot.press(*"One layout", "enter")
        await pilot.pause()

    commands = drive(test, monkeypatch)
    created = tmp_path / "dev" / "rfc" / "one-layout.md"
    rfc = load_rfc(created)
    assert (rfc.title, rfc.status) == ("One layout", "draft")
    assert "## Open questions" in rfc.description
    assert commands[-1][-1] == str(created)


def test_advance_accepts_a_draft_rfc_and_dates_it(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = rfc_file(tmp_path / "dev" / "rfc", "one-layout", "draft")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show_rfc(app, pilot, path)
        assert str(rfc_button(app, "advance").label) == "accepted →"
        rfc_button(app, "advance").press()
        await pilot.pause(0.2)
        assert load_rfc(path).status == "accepted"
        assert "decided" in load_rfc(path).meta

    drive(test, monkeypatch)


def test_the_rfc_tree_folds_the_decided_ones(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "dev" / "rfc"
    draft = rfc_file(folder, "new-design", "draft")
    rfc_file(folder, "old-design", "withdrawn")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        browser = await show_rfc(app, pilot, draft)
        groups = {
            str(node.label).split()[0]: node.is_expanded
            for node in browser.query_one(Tree).root.children
        }
        assert groups == {"draft": True, "withdrawn": False}

    drive(test, monkeypatch)


def test_clicking_a_related_rfc_opens_it(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rfc = rfc_file(tmp_path / "dev" / "rfc", "one-layout", "accepted")
    issue = tmp_path / "dev" / "issues" / "new.md"
    issue.parent.mkdir(parents=True)
    issue.write_text(
        "---\ntype: issue\nstatus: todo\nrelatedTo: [one-layout]\n---\n\n# New\n"
    )

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        app.query_one(TabbedContent).active = "issues"
        await pilot.pause()
        browser = app.query_one("#issues MarkdownBrowser", MarkdownBrowser)
        await browser.open(issue)
        await pilot.pause()
        await pilot.click("#issues MetaBar", offset=(13, 2))
        await pilot.pause()
        assert app.query_one(TabbedContent).active == "rfcs"
        rfcs = app.query_one("#rfcs MarkdownBrowser", MarkdownBrowser)
        assert rfcs.current == rfc

    drive(test, monkeypatch)


def test_the_comments_of_an_rfc_show_as_a_thread(
    config: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = rfc_file(tmp_path / "dev" / "rfc", "one-layout", "draft")
    path.write_text(path.read_text() + "\n---\nby: fabio\n\nWhy not YAML?\n")

    async def test(app: R2App, pilot: Pilot[None]) -> None:
        await show_rfc(app, pilot, path)
        assert len(app.query("#rfcs CommentThread Collapsible")) == 1

    drive(test, monkeypatch)
