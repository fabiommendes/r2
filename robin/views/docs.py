"""Development and user documentation."""

from textual.app import ComposeResult

from robin.project import ProjectContext
from robin.views.base import View
from robin.widgets.markdown import MarkdownBrowser

SECTIONS = {
    "Architecture": "dev/docs",
    "Specs": "dev/spec",
    "Documentation": "docs",
}


class DocsView(View):
    ID = "docs"
    TITLE = "Docs"

    def compose(self) -> ComposeResult:
        yield MarkdownBrowser(SECTIONS)

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(MarkdownBrowser).load(context.root)
