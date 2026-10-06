"""
Tests for plugin panes hosted in the r2 TUI.

Plugins are written into a private config dir and the real app runs under
Textual's pilot, with config, state and the herdr socket pointed at
temporary paths so nothing on the machine is read or written. Plugin tabs
come after r2's own views.
"""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, TabbedContent
from typer.testing import CliRunner

from r2.cli.app import build_app
from r2.core.conf import Config
from r2.core.plugins import loader
from r2.tui.app import R2App
from r2.tui.pane import PluginPane
from r2.tui.plugins import load_panes
from r2.tui.views import View

MANIFEST = """
[plugin]
name = "demo"

[panes.first]
title = "First"

[panes.form]
title = "Form"

[panes.last]
title = "Last"
"""

PLUGIN = """
from textual.widgets import Input, Static
from r2.plugin import Plugin
from r2.tui import PaneCommand, PluginPane

plugin = Plugin("demo")
calls = []


@plugin.pane()
class FirstPane(PluginPane, can_focus=True):
    GLOBAL_COMMANDS = [PaneCommand("ping", "Ping first", key="ctrl+g")]
    LOCAL_COMMANDS = [PaneCommand("hello", "Say hello", key="h")]

    def compose(self):
        yield Static("first")

    def action_ping(self):
        calls.append("ping")

    def action_hello(self):
        calls.append("hello")


@plugin.pane("form")
class FormPane(PluginPane):
    # Takes the same global key as FirstPane: must be skipped and reported.
    GLOBAL_COMMANDS = [PaneCommand("noop", "Clash", key="ctrl+g")]

    def compose(self):
        yield Input(value="abc")

    def action_noop(self):
        calls.append("clash")


@plugin.pane()
class LastPane(PluginPane, can_focus=True):
    def compose(self):
        yield Static("last")
"""


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    (config / "plugins").mkdir(parents=True)
    (config / "config.toml").write_text("")
    monkeypatch.setenv("R2_CONFIG_DIR", str(config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "no-herdr.sock"))
    monkeypatch.delenv("R2_AGENT", raising=False)
    monkeypatch.chdir(tmp_path)
    Config.reset()
    loader.reset()
    return config


def write_plugin(name: str, manifest: str, init: str) -> None:
    root = Path(os.environ["R2_CONFIG_DIR"]) / "plugins" / name
    root.mkdir()
    (root / "plugin.toml").write_text(textwrap.dedent(manifest))
    (root / "__init__.py").write_text(textwrap.dedent(init))


def demo_calls() -> list[str]:
    calls: list[str] = sys.modules["r2_plugins.demo"].calls
    return calls


def drive(test: Callable[[R2App, Pilot[None]], Awaitable[None]]) -> None:
    app = R2App()

    async def main() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            await test(app, pilot)

    asyncio.run(main())


def active(app: R2App) -> str:
    return app.query_one(TabbedContent).active.removeprefix("demo--")


async def show(app: R2App, pilot: Pilot[None], tab: str) -> None:
    app.query_one(TabbedContent).active = tab
    await pilot.pause()


#
# Loading
#
def test_panes_load_in_manifest_order(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)
    entries, problems = load_panes()
    assert [(e.id, e.title) for e in entries] == [
        ("demo--first", "First"),
        ("demo--form", "Form"),
        ("demo--last", "Last"),
    ]
    assert problems == []


def test_broken_plugin_is_skipped_and_others_load(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)
    write_plugin("bad", '[plugin]\nname = "bad"\n[panes.x]\n', "def (:")
    entries, problems = load_panes()
    assert len(entries) == 3
    assert len(problems) == 1 and "SyntaxError" in problems[0].message


def test_pane_mismatches_are_reported(config: Path) -> None:
    write_plugin(
        "odd",
        '[plugin]\nname = "odd"\n[panes.missing]\n[panes.widget]\n',
        """
        from textual.widgets import Static
        from r2.plugin import Plugin
        plugin = Plugin("odd")

        @plugin.pane("widget")
        class NotAPane(Static): ...

        @plugin.pane()
        class ExtraPane(Static): ...
        """,
    )
    entries, problems = load_panes()
    assert entries == []
    messages = " | ".join(p.message for p in problems)
    assert "'missing' is in plugin.toml but not registered" in messages
    assert "'widget' must subclass r2.tui.PluginPane" in messages
    assert "'extra' is registered but missing from plugin.toml" in messages


def test_invalid_pane_name_is_a_manifest_problem(config: Path) -> None:
    write_plugin("demo", '[plugin]\nname = "demo"\n[panes."Two Words"]\n', "")
    entries, problems = load_panes()
    assert entries == [] and "invalid pane name" in problems[0].message


def test_doctor_checks_panes(config: Path) -> None:
    write_plugin("demo", MANIFEST.replace("[panes.last]", "[panes.gone]"), PLUGIN)
    result = CliRunner().invoke(build_app(), ["plugins", "doctor"])
    assert result.exit_code == 1
    assert "'gone' is in plugin.toml but not registered" in result.output


def test_plugin_tabs_come_after_the_views(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        ids = [pane.id for pane in app.query_one(TabbedContent).query("TabPane")]
        assert ids[-3:] == ["demo--first", "demo--form", "demo--last"]
        assert ids[0] == "live"
        assert app.problems == [] or all("ctrl+g" in p for p in app.problems)

    drive(check)


#
# Navigation
#
def test_arrows_move_between_plugin_panes_without_wrapping(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot, "demo--last")
        await pilot.press("right")
        assert active(app) == "last"
        await show(app, pilot, "demo--first")
        await pilot.press("right")
        assert active(app) == "form"
        assert isinstance(app.focused, Input)

    drive(check)


def test_arrows_cross_between_views_and_plugin_panes(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot, "demo--first")
        await pilot.press("left")
        assert active(app) == "issues"
        view = app.query_one("#issues View", View)
        assert app.focused is not None and view in app.focused.ancestors

        # From the issues view, right walks drawer -> content -> next tab.
        for _ in range(4):
            if active(app) != "issues":
                break
            await pilot.press("right")
        assert active(app) == "first"
        assert isinstance(app.focused, PluginPane)

    drive(check)


def test_input_keeps_arrows_until_its_cursor_hits_the_edge(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot, "demo--form")
        field = app.query_one("#demo--form Input", Input)
        field.focus()
        field.cursor_position = 1

        await pilot.press("right", "right")
        assert active(app) == "form" and field.cursor_position == 3
        await pilot.press("right")
        assert active(app) == "last"

        await pilot.press("left")
        assert active(app) == "form"
        field.cursor_position = 1
        await pilot.press("left")
        assert active(app) == "form" and field.cursor_position == 0
        await pilot.press("left")
        assert active(app) == "first"

    drive(check)


def test_alt_arrows_always_move(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot, "demo--form")
        app.query_one("#demo--form Input", Input).cursor_position = 1
        await pilot.press("alt+right")
        assert active(app) == "last"
        await pilot.press("alt+right")
        assert active(app) == "last"

    drive(check)


#
# Commands
#
def test_local_binding_only_while_pane_is_active(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        await show(app, pilot, "demo--first")
        await pilot.press("h")
        assert demo_calls() == ["hello"]
        await pilot.press("alt+right", "alt+right", "h")
        assert demo_calls() == ["hello"]

    drive(check)


def test_global_binding_runs_on_its_pane_from_anywhere(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        assert active(app) == "live"
        await pilot.press("ctrl+g")
        await pilot.pause()
        assert demo_calls() == ["ping"]
        assert active(app) == "live"

    drive(check)


def test_clashing_global_key_is_reported(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        assert any("'ctrl+g'" in p and "demo--form" in p for p in app.problems)

    drive(check)


def test_global_key_cannot_take_an_app_key(config: Path) -> None:
    write_plugin(
        "demo",
        MANIFEST,
        PLUGIN.replace('key="ctrl+g")]\n    LOCAL', 'key="q")]\n    LOCAL'),
    )

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        assert any("'q'" in p and "demo--first" in p for p in app.problems)

    drive(check)


def test_palette_has_globals_and_only_active_locals(config: Path) -> None:
    write_plugin("demo", MANIFEST, PLUGIN)

    async def check(app: R2App, pilot: Pilot[None]) -> None:
        def titles() -> set[str]:
            return {c.title for c in app.get_system_commands(app.screen)}

        await show(app, pilot, "demo--first")
        assert {"First: Ping first", "Form: Clash", "First: Say hello"} <= titles()
        await pilot.press("alt+right")
        assert "First: Say hello" not in titles()
        assert "First: Ping first" in titles()

    drive(check)
