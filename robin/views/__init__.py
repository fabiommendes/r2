"""Robin's views, in tab order.

To add a view, subclass `View` in a new module and append it to `VIEWS`.
"""

from robin.views.base import View
from robin.views.docs import DocsView
from robin.views.issues import IssuesView
from robin.views.live import LiveView
from robin.views.project import ProjectView

VIEWS: list[type[View]] = [LiveView, ProjectView, DocsView, IssuesView]

__all__ = ["VIEWS", "View"]
