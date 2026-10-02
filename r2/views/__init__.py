"""R2's views, in tab order.

To add a view, subclass `View` in a new module and append it to `VIEWS`.
"""

from r2.views.base import View
from r2.views.docs import DocsView
from r2.views.issues import IssuesView
from r2.views.live import LiveView
from r2.views.project import ProjectView

VIEWS: list[type[View]] = [LiveView, ProjectView, DocsView, IssuesView]

__all__ = ["VIEWS", "View"]
