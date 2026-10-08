"""Issues kept as markdown files in the project."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.binding import Binding

from r2.core.issues import FORMAT, Issue, slugify
from r2.tui.views.threads import ThreadsView, related_links, status_pill
from r2.tui.widgets.issue_form import IssueForm
from r2.tui.widgets.meta import FieldRenderer, render_value


def unless_normal(value: Any, colors: dict[str, str]) -> Text | None:
    """Leave out the "normal" value, as the issue files do."""
    return None if value == "normal" else render_value(value)


def issue_fields(project_root: Callable[[], Path | None]) -> dict[str, FieldRenderer]:
    """How the issue browser renders the frontmatter of issues."""
    return {
        "status": status_pill,
        "priority": unless_normal,
        "severity": unless_normal,
        "relatedTo": related_links(project_root),
    }


def free_path(folder: Path, slug: str) -> Path:
    """Return folder/slug.md, numbered if that file already exists."""
    path = folder / f"{slug}.md"
    number = 2
    while path.exists():
        path = folder / f"{slug}-{number}.md"
        number += 1
    return path


class IssuesView(ThreadsView):
    ID = "issues"
    TITLE = "Issues"
    FORMAT = FORMAT

    BINDINGS = [Binding("n", "new_issue", "New issue")]

    def fields(
        self, project_root: Callable[[], Path | None]
    ) -> dict[str, FieldRenderer]:
        return issue_fields(project_root)

    def action_new_issue(self) -> None:
        self.app.push_screen(IssueForm(), self._create)

    def _create(self, issue: Issue | None) -> None:
        if issue is not None:
            self.create(issue, lambda folder: free_path(folder, slugify(issue.title)))
