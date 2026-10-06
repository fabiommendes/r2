"""R2's Textual application."""

import asyncio
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from textual import events
from textual.app import App, ComposeResult, SuspendNotSupported, SystemCommand
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Static, TabbedContent, TabPane

from r2.core import git
from r2.core.editor import (
    editor_command,
    ide_command,
    launch_detached,
    open_externally,
    shell_command,
)
from r2.core.links import Link
from r2.core.project import ProjectContext, Projects
from r2.core.state import UIState
from r2.integrations import herdr
from r2.integrations.claude.events import event_links, tail
from r2.integrations.claude.notify import events_path
from r2.tui import theme
from r2.tui.pane import Direction, PaneCommand, PluginPane
from r2.tui.plugins import PaneEntry, load_panes
from r2.tui.views import VIEWS, View
from r2.tui.widgets.preview import FilePreview
from r2.tui.widgets.splitter import Splitter

MAX_RECONNECT_DELAY = 30.0

GIT_POLL_INTERVAL = 5.0

# Theme variables that color the top bar segments.
PROJECT_COLOR = "accent"
PINNED_COLOR = "primary"
WORKTREE_COLORS = {
    git.Worktree.DIRTY: "error",
    git.Worktree.STAGED: "success",
    git.Worktree.CLEAN: "panel-lighten-2",
}


#: Keys that plugin global commands cannot take, besides the app's own.
RESERVED_KEYS = {"left", "right", "alt+left", "alt+right", "ctrl+q", "ctrl+p"}

PALETTE_ICON = "⭘"
PALETTE_COLOR = "secondary"


class TopBar(Static):
    """Powerline title bar whose first segment opens the command palette."""

    # The palette segment: the icon padded by spaces, plus the arrow.
    PALETTE_WIDTH = len(PALETTE_ICON) + 3

    def on_click(self, event: events.Click) -> None:
        if event.x < self.PALETTE_WIDTH:
            self.app.action_command_palette()


class R2App(App[None]):
    """Follow the Claude session in the herdr pane that has focus."""

    TITLE = "r2"
    CSS = (
        theme.CSS
        + """
    #topbar {
        dock: top;
        height: 1;
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
        Binding("f5", "refresh", "Refresh", show=False),
        *(
            Binding(str(number), f"show_view('{view.ID}')", view.TITLE, show=False)
            for number, view in enumerate(VIEWS, start=1)
        ),
    ]

    context: reactive[ProjectContext | None] = reactive(None)
    git_status: reactive[git.GitStatus | None] = reactive(None)
    pinned: reactive[bool] = reactive(False)
    """Stay on the current project instead of following herdr focus."""

    def __init__(
        self,
        plugin_panes: list[PaneEntry] | None = None,
        problems: list[str] | None = None,
    ) -> None:
        theme.install()
        super().__init__()
        self.projects = Projects()
        self.ui_state = UIState.load()
        if plugin_panes is None:
            plugin_panes, found = load_panes()
            problems = [*(problems or []), *map(str, found)]
        self.plugin_panes = plugin_panes
        #: Plugin load problems, shown as notifications once the app is up.
        self.problems = list(problems or [])
        #: Arrow that led to the tab being activated, for `PluginPane.enter`.
        self.entry_direction: Direction | None = None
        self.bind_global_commands()

    def compose(self) -> ComposeResult:
        yield TopBar(id="topbar")
        with TabbedContent():
            for number, view in enumerate(VIEWS, start=1):
                with TabPane(f"{number} {view.TITLE}", id=view.ID):
                    yield view()
            for entry in self.plugin_panes:
                with TabPane(entry.title, id=entry.id):
                    pane = entry.cls()
                    pane.pane_id = entry.id
                    pane.title = entry.title
                    yield pane
        yield Footer()

    def on_mount(self) -> None:
        if self.ui_state.theme in self.available_themes:
            self.theme = self.ui_state.theme
        self.theme_changed_signal.subscribe(self, self._on_theme_changed)
        for splitter in self.query(Splitter):
            splitter.target.styles.width = self.ui_state.drawer_width(splitter.key)
        self.context = self.projects.get(Path.cwd())
        self._focus_entry(self._active_view())
        for problem in self.problems:
            self.notify(problem, title="plugin skipped", severity="warning", timeout=10)
        self.run_worker(self._follow_herdr(), exclusive=True, group="herdr")
        self.run_worker(self._follow_events(), group="events")
        self.run_worker(self._poll_git(), group="git-poll")

    def on_splitter_resized(self, event: Splitter.Resized) -> None:
        self.ui_state.drawer_widths[event.splitter.key] = event.width
        try:
            self.ui_state.save()
        except OSError:
            self.notify("Could not save the UI state", severity="warning")

    def watch_context(self, context: ProjectContext | None) -> None:
        if context is None:
            return
        self.git_status = None
        self.refresh_git()
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

    def watch_git_status(self) -> None:
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        colors = self.get_css_variables()
        segments = [
            (PALETTE_ICON, colors[PALETTE_COLOR]),
            (self.context.name if self.context else "", colors[PROJECT_COLOR]),
        ]
        if self.git_status is not None:
            branch = f"{theme.BRANCH_SYMBOL} {self.git_status.branch}"
            worktree = WORKTREE_COLORS[self.git_status.worktree]
            segments.append((branch, colors[worktree]))
        if self.pinned:
            segments.append(("pinned", colors[PINNED_COLOR]))
        self.query_one(TopBar).update(theme.powerline(*segments))

    def _on_theme_changed(self, _: object) -> None:
        if self.theme != self.ui_state.theme:
            self.ui_state.theme = self.theme
            try:
                self.ui_state.save()
            except OSError:
                self.notify("Could not save the UI state", severity="warning")
        self._update_subtitle()

    def refresh_git(self) -> None:
        """Read the git status of the current project again."""
        self.run_worker(self._refresh_git(), exclusive=True, group="git")

    async def _refresh_git(self) -> None:
        root = self.context.root if self.context else None
        try:
            result = await git.status(root) if root else None
        except OSError:
            result = None
        if self.context is not None and self.context.root == root:
            self.git_status = result

    async def _poll_git(self) -> None:
        while True:
            await asyncio.sleep(GIT_POLL_INTERVAL)
            self.refresh_git()

    def action_show_view(self, view_id: str) -> None:
        self.query_one(TabbedContent).active = view_id

    def _active_view(self) -> View | PluginPane:
        tabs = self.query_one(TabbedContent)
        pane = tabs.get_pane(tabs.active)
        for widget in pane.children:
            if isinstance(widget, View | PluginPane):
                return widget
        raise NoMatches(f"no view in tab {tabs.active!r}")

    def _focus_entry(self, view: View | PluginPane) -> None:
        if isinstance(view, View):
            view.focus_entry()
        else:
            view.enter(self.entry_direction)
        self.entry_direction = None

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        self._focus_entry(self._active_view())
        self.refresh_bindings()

    #
    # Plugin panes
    #
    def plugin_pane(self, pane_id: str) -> PluginPane:
        return self.query_one(f"#{pane_id}", TabPane).query_one(PluginPane)

    def bind_global_commands(self) -> None:
        """
        Bind every plugin pane's global command keys on the app. A key that
        is reserved or already taken is skipped and reported; the command
        stays in the palette.
        """
        taken = RESERVED_KEYS | {
            key for key, _ in self._bindings.key_to_bindings.items()
        }
        for entry in self.plugin_panes:
            for cmd in entry.cls.GLOBAL_COMMANDS:
                if cmd.key is None:
                    continue
                if cmd.key in taken:
                    self.problems.append(
                        f"{entry.id}: key {cmd.key!r} for {cmd.title!r} is taken"
                    )
                    continue
                taken.add(cmd.key)
                self.bind(
                    cmd.key,
                    f"pane_run({entry.id!r}, {cmd.action!r})",
                    description=cmd.title,
                    show=cmd.show,
                )

    async def action_pane_run(self, pane_id: str, action: str) -> None:
        """Run a plugin global command on its pane."""
        await self.plugin_pane(pane_id).run_action(action)

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        try:
            active = self._active_view()
        except NoMatches:
            return
        for pane in self.query(PluginPane):
            for cmd in pane.GLOBAL_COMMANDS:
                yield self._system_command(pane, cmd)
            if pane is active:
                for cmd in pane.LOCAL_COMMANDS:
                    yield self._system_command(pane, cmd)

    def _system_command(self, pane: PluginPane, cmd: PaneCommand) -> SystemCommand:
        async def run() -> None:
            await pane.run_action(cmd.action)

        return SystemCommand(f"{pane.title}: {cmd.title}", cmd.help, run)

    def _hand_over(self, command: list[str], cwd: Path | None = None) -> None:
        """Give the terminal to command and take it back when it exits."""
        try:
            with self.suspend():
                subprocess.run(command, cwd=cwd, check=False)
        except OSError as error:
            self.notify(f"Could not run {command[0]}: {error}", severity="error")
        except SuspendNotSupported:
            self.notify("This terminal cannot be handed over to another program")
        self.refresh_git()

    def action_edit(self) -> None:
        """Open the current file in the terminal editor, then come back."""
        link = self._active_view().current_link()
        if link is not None:
            self._edit(link)

    def on_view_edit_file(self, message: View.EditFile) -> None:
        self._edit(message.link)

    def _edit(self, link: Link) -> None:
        self._hand_over(editor_command(link))
        self._active_view().reload()

    def action_shell(self) -> None:
        """Run an interactive shell in the project root; exiting it returns here."""
        root = self.context.root if self.context else Path.cwd()
        self._hand_over(shell_command(), cwd=root)
        self._active_view().reload()

    def action_refresh(self) -> None:
        """Read the files on screen and the git status again."""
        self._active_view().reload()
        self.refresh_git()

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

    def _active_previews(self) -> list[FilePreview]:
        try:
            tabs = self.query_one(TabbedContent)
        except NoMatches:
            return []
        return list(tabs.query(f"#{tabs.active} FilePreview").results(FilePreview))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # None shows the binding dimmed in the footer instead of hiding it.
        if action == "toggle_full":
            return any(p.can_toggle for p in self._active_previews()) or None
        return True

    def action_toggle_full(self) -> None:
        """Toggle the file preview of the active view, if it has one."""
        for preview in self._active_previews():
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
        if context is self.context and event.get("hook_event_name") == "Stop":
            self.refresh_git()
        links = await event_links(event, context.root)
        if not links:
            return
        context.add_links(links)
        if context is self.context:
            for view in self.query(View):
                view.links_changed()


def main() -> None:
    R2App().run()
