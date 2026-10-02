"""Robin's Textual application."""

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Footer, Static, TabbedContent, TabPane

from robin import herdr, theme
from robin.config import Config
from robin.editor import (
    editor_command,
    ide_command,
    launch_detached,
    open_externally,
    shell_command,
)
from robin.events import tail
from robin.links import extract_links, link_from_read
from robin.notify import events_path
from robin.project import ProjectContext, Projects
from robin.transcript import last_turn_text
from robin.views import VIEWS, View
from robin.widgets.preview import FilePreview
from robin.widgets.splitter import Splitter

MAX_RECONNECT_DELAY = 30.0

# Claude may still be writing the transcript when the Stop hook fires.
TRANSCRIPT_SETTLE_DELAY = 0.5


class RobinApp(App[None]):
    """Follow the Claude session in the herdr pane that has focus."""

    TITLE = "robin"
    CSS = (
        theme.CSS
        + """
    #title {
        height: 1;
        padding: 0 1;
    }
    """
    )

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "toggle_pin", "Pin project"),
        Binding("f", "toggle_full", "Excerpt/full"),
        Binding("e", "edit", "Edit"),
        Binding("o", "open", "Open"),
        Binding("i", "ide", "IDE"),
        Binding("t", "shell", "Shell"),
        *(
            Binding(str(number), f"show_view('{view.ID}')", view.TITLE, show=False)
            for number, view in enumerate(VIEWS, start=1)
        ),
    ]

    context: reactive[ProjectContext | None] = reactive(None)
    pinned: reactive[bool] = reactive(False)
    """Stay on the current project instead of following herdr focus."""

    def __init__(self) -> None:
        theme.install()
        super().__init__()
        self.projects = Projects()
        self.config = Config.load()

    def compose(self) -> ComposeResult:
        yield Static(id="title")
        with TabbedContent():
            for number, view in enumerate(VIEWS, start=1):
                with TabPane(f"{number} {view.TITLE}", id=view.ID):
                    yield view()
        yield Footer()

    def on_mount(self) -> None:
        for splitter in self.query(Splitter):
            splitter.target.styles.width = self.config.drawer_width(splitter.key)
        self.context = self.projects.get(Path.cwd())
        self._active_view().focus_drawer()
        self.run_worker(self._follow_herdr(), exclusive=True, group="herdr")
        self.run_worker(self._follow_events(), group="events")

    def on_splitter_resized(self, event: Splitter.Resized) -> None:
        self.config.drawer_widths[event.splitter.key] = event.width
        try:
            self.config.save()
        except OSError:
            self.notify("Could not save the config", severity="warning")

    def watch_context(self, context: ProjectContext | None) -> None:
        if context is None:
            return
        for view in self.query(View):
            # A focus event may land while the app is shutting down and the
            # views have already lost their children.
            try:
                view.set_context(context)
            except NoMatches:
                return
        self._update_subtitle()

    def watch_pinned(self) -> None:
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        name = self.context.name if self.context else ""
        pinned = "  [dim](pinned)[/]" if self.pinned else ""
        self.query_one("#title", Static).update(f"[b]{name}[/]{pinned}")

    def action_show_view(self, view_id: str) -> None:
        self.query_one(TabbedContent).active = view_id

    def _active_view(self) -> View:
        tabs = self.query_one(TabbedContent)
        return tabs.query_one(f"#{tabs.active} View", View)

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        event.pane.query_one(View).focus_entry()

    def _hand_over(self, command: list[str], cwd: Path | None = None) -> None:
        """Give the terminal to command and take it back when it exits."""
        try:
            with self.suspend():
                subprocess.run(command, cwd=cwd, check=False)
        except OSError as error:
            self.notify(f"Could not run {command[0]}: {error}", severity="error")
        except SuspendNotSupported:
            self.notify("This terminal cannot be handed over to another program")

    def action_edit(self) -> None:
        """Open the current file in the terminal editor, then come back."""
        view = self._active_view()
        link = view.current_link()
        if link is None:
            return
        self._hand_over(editor_command(link))
        for preview in view.query(FilePreview):
            preview.reload()

    def action_shell(self) -> None:
        """Run an interactive shell in the project root; exiting it returns here."""
        root = self.context.root if self.context else Path.cwd()
        self._hand_over(shell_command(), cwd=root)
        for preview in self._active_view().query(FilePreview):
            preview.reload()

    def action_open(self) -> None:
        """Open the current file in its default application (xdg-open)."""
        link = self._active_view().current_link()
        if link is None:
            return
        try:
            open_externally(link.path)
        except OSError as error:
            self.notify(f"Could not open {link.path.name}: {error}", severity="error")

    def action_ide(self) -> None:
        """Open the project root in the GUI editor."""
        root = self.context.root if self.context else Path.cwd()
        command = ide_command(root)
        try:
            launch_detached(command)
        except OSError as error:
            self.notify(f"Could not run {command[0]}: {error}", severity="error")

    def action_toggle_full(self) -> None:
        """Toggle the file preview of the active view, if it has one."""
        tabs = self.query_one(TabbedContent)
        for preview in tabs.query(f"#{tabs.active} FilePreview").results(FilePreview):
            preview.toggle_full()

    async def action_toggle_pin(self) -> None:
        self.pinned = not self.pinned
        if not self.pinned:
            self.run_worker(self._focus_current_pane(), group="herdr-sync")

    async def _focus_current_pane(self) -> None:
        try:
            pane_id = await herdr.focused_pane_id()
            if pane_id:
                await self._focus_pane(pane_id)
        except (OSError, ValueError, herdr.HerdrError):
            pass

    async def _focus_pane(self, pane_id: str) -> None:
        if self.pinned:
            return
        pane = await herdr.get_pane(pane_id)
        context = self.projects.get(pane.cwd)
        if context is not self.context:
            self.context = context

    async def _follow_herdr(self) -> None:
        """Track herdr focus, reconnecting whenever herdr goes away."""
        delay = 1.0
        while True:
            try:
                await self._focus_current_pane()
                async for pane_id in herdr.focus_events():
                    delay = 1.0
                    await self._focus_pane(pane_id)
            except (OSError, ValueError, herdr.HerdrError):
                pass
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    async def _follow_events(self) -> None:
        async for event in tail(events_path()):
            try:
                await self._handle_event(event)
            except (OSError, ValueError, KeyError, TypeError):
                continue

    async def _handle_event(self, event: dict[str, Any]) -> None:
        context = self.projects.get(Path(event["cwd"]))
        match event.get("hook_event_name"):
            case "PostToolUse" if event.get("tool_name") == "Read":
                link = link_from_read(event["tool_input"])
                links = [link] if link else []
            case "Stop":
                links = extract_links(await self._turn_text(event), context.root)
            case _:
                return
        if not links:
            return
        context.add_links(links)
        if context is self.context:
            for view in self.query(View):
                view.links_changed()

    async def _turn_text(self, event: dict[str, Any]) -> str:
        text: str | None = event.get("last_assistant_message")
        if text:
            return text
        if time.time() - event.get("robin_time", 0) < TRANSCRIPT_SETTLE_DELAY:
            await asyncio.sleep(TRANSCRIPT_SETTLE_DELAY)
        path = Path(event["transcript_path"])
        return await asyncio.to_thread(last_turn_text, path)


def main() -> None:
    RobinApp().run()
