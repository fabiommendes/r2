"""Issues kept as markdown files in the project."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding

from robin.issues import Issue, render, slugify
from robin.links import Link
from robin.project import ProjectContext
from robin.views.base import View
from robin.widgets.issue_form import IssueForm
from robin.widgets.markdown import MarkdownBrowser

ISSUES_DIR = "dev/issues"
SECTIONS = {"Issues": ISSUES_DIR}


def free_path(folder: Path, slug: str) -> Path:
    """Return folder/slug.md, numbered if that file already exists."""
    path = folder / f"{slug}.md"
    number = 2
    while path.exists():
        path = folder / f"{slug}-{number}.md"
        number += 1
    return path


def first_section_line(text: str) -> int:
    """The line below the first level 2 heading, where writing starts."""
    lines = text.splitlines()
    for number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            return number + 2
    return len(lines)


class IssuesView(View):
    ID = "issues"
    TITLE = "Issues"

    BINDINGS = [Binding("n", "new_issue", "New issue")]

    def compose(self) -> ComposeResult:
        yield MarkdownBrowser(self.ID, SECTIONS)

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(MarkdownBrowser).load(context.root)

    def current_link(self) -> Link | None:
        path = self.query_one(MarkdownBrowser).current
        return Link(path) if path else None

    def reload(self) -> None:
        if self.context is not None:
            browser = self.query_one(MarkdownBrowser)
            self.run_worker(browser.reload(self.context.root))

    def action_new_issue(self) -> None:
        self.app.push_screen(IssueForm(), self._create)

    def _create(self, issue: Issue | None) -> None:
        if issue is None or self.context is None:
            return
        folder = self.context.root / ISSUES_DIR
        text = render(issue)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = free_path(folder, slugify(issue.title))
            path.write_text(text)
        except OSError as error:
            self.notify(f"Could not create the issue: {error}", severity="error")
            return
        self.query_one(MarkdownBrowser).current = path
        self.post_message(self.EditFile(Link(path, first_section_line(text))))
