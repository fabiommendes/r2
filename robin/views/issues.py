"""Issues kept as markdown files in the project."""

from textual.app import ComposeResult

from robin.project import ProjectContext
from robin.views.base import View
from robin.widgets.markdown import MarkdownBrowser

SECTIONS = {"Issues": "dev/issues"}


class IssuesView(View):
    ID = "issues"
    TITLE = "Issues"

    def compose(self) -> ComposeResult:
        yield MarkdownBrowser(SECTIONS)

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(MarkdownBrowser).load(context.root)
