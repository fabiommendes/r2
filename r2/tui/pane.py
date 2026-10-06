"""
Base class for plugin panes.

```python
from textual.widgets import DataTable
from r2.tui import PaneCommand, PluginPane

@plugin.pane()
class AliasesPane(PluginPane):
    GLOBAL_COMMANDS = [
        PaneCommand("reload", "Reload aliases", key="ctrl+r"),
    ]
    LOCAL_COMMANDS = [
        PaneCommand("add", "Add alias", key="a"),
    ]

    def compose(self):
        yield DataTable()

    def action_reload(self) -> None: ...
    def action_add(self) -> None: ...
```

Navigation: plugin panes are tabs after r2's own views. The arrow keys move
to the neighbor tab when `should_leave()` says so, and otherwise reach the
focused widget as usual. `alt+left` / `alt+right` always move.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from textual.actions import SkipAction
from textual.binding import Binding, BindingType
from textual.widget import Widget
from textual.widgets import DataTable, Input, TabbedContent, TabPane, TextArea

from r2.core.links import Link

__all__ = ["Direction", "PaneCommand", "PluginPane", "focus_at_edge"]

type Direction = Literal["left", "right"]


@dataclass(frozen=True)
class PaneCommand:
    """
    A pane action exposed as a key binding and as a command palette entry.
    """

    #: Action on the pane, as in Textual bindings: "reload" calls
    #: `action_reload`; "open('x')" passes arguments.
    action: str
    #: Label in the footer and in the command palette.
    title: str
    help: str = ""
    #: Key binding, in Textual syntax ("a", "ctrl+r"). Palette-only when None.
    key: str | None = None
    #: Show the binding in the footer.
    show: bool = True

    def binding(self) -> Binding:
        assert self.key is not None
        return Binding(self.key, self.action, self.title, show=self.show)


class PluginPane(Widget):
    """
    A widget contributed by a plugin to the r2 TUI.

    Subclasses declare two lists of commands:

    - `GLOBAL_COMMANDS`: bound on the whole app; they run on this pane even
      when another pane is active. Call `self.activate()` from the action to
      bring the pane forward.
    - `LOCAL_COMMANDS`: bound only while focus is inside this pane, and
      offered in the command palette only while it is the active pane.

    Plain Textual `BINDINGS` still work and behave like local commands
    without a palette entry.
    """

    DEFAULT_CSS = """
    PluginPane {
        height: 1fr;
    }
    """

    # Priority bindings, so they win over widgets that use arrows themselves.
    # `navigate` raises SkipAction to hand the key back to the focused widget.
    BINDINGS = [
        Binding("left", "navigate('left')", show=False, priority=True),
        Binding("right", "navigate('right')", show=False, priority=True),
        Binding("alt+left", "navigate('left', True)", "Prev tab", priority=True),
        Binding("alt+right", "navigate('right', True)", "Next tab", priority=True),
    ]

    GLOBAL_COMMANDS: ClassVar[list[PaneCommand]] = []
    LOCAL_COMMANDS: ClassVar[list[PaneCommand]] = []

    #: Set by the TUI when the pane is created.
    pane_id: str = ""
    #: Tab label, from the plugin manifest.
    title: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Textual merges BINDINGS when the class is created, so local command
        # keys must be in place before `super().__init_subclass__()` runs.
        own: list[BindingType] = list(cls.__dict__.get("BINDINGS", []))
        local = cls.__dict__.get("LOCAL_COMMANDS", [])
        cls.BINDINGS = own + [cmd.binding() for cmd in local if cmd.key]
        super().__init_subclass__(**kwargs)

    #
    # Navigation hooks
    #
    def should_leave(self, direction: Direction) -> bool:
        """
        Whether an arrow key in `direction` moves to the neighbor pane.

        The default leaves unless the focused widget can still move its own
        cursor that way (see `focus_at_edge`). Override for custom widgets.
        """
        focused = self.screen.focused
        # The pane itself binds the arrows for navigation, so it never keeps them.
        if focused is None or focused is self or self not in focused.ancestors:
            return True
        return focus_at_edge(focused, direction)

    def enter(self, direction: Direction | None) -> None:
        """
        Called after the pane becomes active. `direction` is the arrow that
        brought the user here, or None for a jump (tab click, `activate()`).

        The default focuses the pane itself, or its first focusable widget.
        """
        if self.focusable:
            self.focus()
            return
        for widget in self.query("*"):
            if widget.focusable:
                widget.focus()
                return

    def activate(self) -> None:
        """
        Make this the active tab.
        """
        self.query_ancestor(TabbedContent).active = self.tab().id or ""

    def tab(self) -> TabPane:
        return self.query_ancestor(TabPane)

    def action_navigate(self, direction: Direction, force: bool = False) -> None:
        """
        Move to the neighbor tab, unless this pane keeps the key.
        """
        if not force and not self.should_leave(direction):
            raise SkipAction()
        if not switch_tab(self.tab(), direction) and not force:
            raise SkipAction()

    #
    # Hooks shared with r2's views
    #
    def current_link(self) -> Link | None:
        """
        The file the pane is showing, for the app's edit and open commands.
        """
        return None

    def reload(self) -> None:
        """
        Read the data on screen again, for instance after an edit (F5).
        """


def switch_tab(tab: TabPane, direction: Direction) -> bool:
    """
    Activate the tab next to `tab`. Returns False at either end.

    Sets `entry_direction` on the app, so the next tab knows where the user
    came from.
    """
    tabs = tab.query_ancestor(TabbedContent)
    panes = list(tabs.query(TabPane))
    index = panes.index(tab) + (-1 if direction == "left" else 1)
    if not 0 <= index < len(panes):
        return False
    tab.app.entry_direction = direction  # type: ignore[attr-defined]
    tabs.active = panes[index].id or ""
    return True


def focus_at_edge(widget: Widget, direction: Direction) -> bool:
    """
    Whether `widget` has nothing left to do with a horizontal arrow key.

    Knows the stock Textual widgets that use left/right themselves. Any other
    widget is at the edge unless it binds the key, in which case it keeps it
    and the user moves with `alt+left` / `alt+right`.
    """
    match widget:
        case Input():
            return (
                widget.cursor_at_start if direction == "left" else widget.cursor_at_end
            )
        case TextArea():
            if direction == "left":
                return widget.cursor_at_start_of_text
            return widget.cursor_at_end_of_text
        case DataTable():
            if widget.cursor_type not in ("cell", "column"):
                return True
            last = max(len(widget.columns) - 1, 0)
            return widget.cursor_column == (0 if direction == "left" else last)
        case _:
            return direction not in widget._bindings.key_to_bindings
