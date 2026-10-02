"""R2's views, in tab order.

To add a view, subclass `View` in a new module and append it to `VIEWS`.
"""

from r2.tui.views.base import View
from r2.tui.views.docs import DocsView
from r2.tui.views.issues import IssuesView
from r2.tui.views.live import LiveView
from r2.tui.views.project import ProjectView

VIEWS: list[type[View]] = [LiveView, ProjectView, DocsView, IssuesView]

__all__ = ["VIEWS", "View"]
