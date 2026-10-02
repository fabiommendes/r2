"""Base class for robin's views."""

from typing import ClassVar

from textual.widget import Widget

from robin.links import Link
from robin.project import ProjectContext


class View(Widget):
    """A tab of robin.

    The app calls the hooks below; subclasses override the ones they need.
    Views keep their per-project state in `ProjectContext.view_state`, under
    their own `ID`, so switching projects back and forth restores it.
    """

    ID: ClassVar[str]
    TITLE: ClassVar[str]

    DEFAULT_CSS = """
    View {
        height: 1fr;
        layout: horizontal;
    }
    """

    context: ProjectContext | None = None

    def set_context(self, context: ProjectContext) -> None:
        """Called when robin switches to another project."""
        self.context = context

    def links_changed(self) -> None:
        """Called when new links arrive for the current project."""

    def current_link(self) -> Link | None:
        """The file the view is showing, used to open it in an editor."""
        return None

    def focus_drawer(self) -> None:
        """Focus the first focusable widget, which is the drawer on the left."""
        for widget in self.query("*"):
            if widget.focusable:
                widget.focus()
                return
