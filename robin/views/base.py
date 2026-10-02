"""Base class for robin's views."""

from typing import ClassVar, Literal

from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import TabbedContent, TabPane

from robin.links import Link
from robin.project import ProjectContext
from robin.widgets.splitter import Splitter


class View(Widget):
    """A tab of robin.

    The app calls the hooks below; subclasses override the ones they need.
    Views keep their per-project state in `ProjectContext.view_state`, under
    their own `ID`, so switching projects back and forth restores it.

    A view has a drawer on the left and content on the right, separated by a
    `Splitter`. Left and right arrows walk the chain drawer 1, content 1,
    drawer 2, content 2... across all tabs.
    """

    # Priority bindings, so they win over widgets that use arrows themselves,
    # like the tab bar and the preview's cursor.
    BINDINGS = [
        Binding("left", "navigate(-1)", show=False, priority=True),
        Binding("right", "navigate(1)", show=False, priority=True),
    ]

    ID: ClassVar[str]
    TITLE: ClassVar[str]

    DEFAULT_CSS = """
    View {
        height: 1fr;
        layout: horizontal;
    }
    """

    context: ProjectContext | None = None

    entry_focus: Literal["drawer", "content"] = "drawer"
    """Where the focus goes the next time the view's tab is activated."""

    def set_context(self, context: ProjectContext) -> None:
        """Called when robin switches to another project."""
        self.context = context

    def links_changed(self) -> None:
        """Called when new links arrive for the current project."""

    def current_link(self) -> Link | None:
        """The file the view is showing, used to open it in an editor."""
        return None

    def drawer_forward(self) -> bool:
        """Handle the right arrow inside the drawer.

        Return True to keep the focus in the drawer, False to move it to the
        content.
        """
        return False

    def focus_drawer(self) -> None:
        if drawer := self._drawer():
            drawer.focus()

    def focus_content(self) -> None:
        if content := self._content():
            content.focus()

    def focus_entry(self) -> None:
        """Focus the side requested by `entry_focus`, then reset it."""
        if self.entry_focus == "content":
            self.focus_content()
        else:
            self.focus_drawer()
        self.entry_focus = "drawer"

    def _drawer(self) -> Widget | None:
        """The first focusable widget, which is the drawer on the left."""
        return next((w for w in self.query("*").results(Widget) if _can_focus(w)), None)

    def _content(self) -> Widget | None:
        """The first focusable widget to the right of the splitter."""
        splitter = self.query_one(Splitter)
        assert splitter.parent is not None
        siblings = list(splitter.parent.children)
        for sibling in siblings[siblings.index(splitter) + 1 :]:
            for widget in [sibling, *sibling.query("*").results(Widget)]:
                if _can_focus(widget):
                    return widget
        return None

    def _in_drawer(self) -> bool:
        focused = self.app.focused
        drawer = self._drawer()
        if focused is None or drawer is None:
            return True
        return focused is drawer or drawer in focused.ancestors

    def action_navigate(self, step: int) -> None:
        in_drawer = self._in_drawer()
        if step > 0 and in_drawer:
            if not self.drawer_forward():
                self.focus_content()
        elif step < 0 and not in_drawer:
            self.focus_drawer()
        else:
            self._switch_tab(step, "drawer" if step > 0 else "content")

    def _switch_tab(self, step: int, entry: Literal["drawer", "content"]) -> None:
        tabs = self.query_ancestor(TabbedContent)
        panes = list(tabs.query(TabPane))
        index = [pane.id for pane in panes].index(tabs.active) + step
        if 0 <= index < len(panes):
            panes[index].query_one(View).entry_focus = entry
            tabs.active = panes[index].id or ""


def _can_focus(widget: Widget) -> bool:
    return widget.focusable and widget.display
