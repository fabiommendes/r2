"""Development and user documentation."""

from textual.app import ComposeResult

from r2.core.project import ProjectContext
from r2.tui.views.base import View
from r2.tui.widgets.markdown import MarkdownBrowser

SECTIONS = {
    "Architecture": "dev/docs",
    "Specs": "dev/spec",
    "Documentation": "docs",
}


class DocsView(View):
    ID = "docs"
    TITLE = "Docs"

    def compose(self) -> ComposeResult:
        yield MarkdownBrowser(self.ID, SECTIONS)

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(MarkdownBrowser).load(context.root)
