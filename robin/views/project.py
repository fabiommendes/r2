"""File browser for the current project."""

from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import DirectoryTree

from robin.links import Link
from robin.project import ProjectContext
from robin.views.base import View
from robin.widgets.preview import FilePreview
from robin.widgets.splitter import Splitter

IGNORED = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


class ProjectTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.name not in IGNORED]


class ProjectView(View):
    ID = "project"
    TITLE = "Project"

    DEFAULT_CSS = """
    ProjectView > ProjectTree {
        height: 1fr;
    }
    ProjectView > FilePreview {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield ProjectTree(Path.cwd())
        yield Splitter(self.ID)
        yield FilePreview()

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(ProjectTree).path = context.root
        self._show(context.view_state.get(self.ID))

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        if self.context is not None:
            self.context.view_state[self.ID] = event.path
        self._show(event.path)

    def _show(self, path: Path | None) -> None:
        preview = self.query_one(FilePreview)
        if path is None or self.context is None:
            preview.show(None)
        else:
            preview.show(Link(path), Link(path).label(self.context.root))
