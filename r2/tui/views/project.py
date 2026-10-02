"""File browser for the current project."""

import subprocess
from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.widgets import DirectoryTree

from r2.core.links import Link
from r2.core.project import ProjectContext
from r2.tui import theme
from r2.tui.views.base import View
from r2.tui.widgets.markdown import MarkdownPane
from r2.tui.widgets.preview import FilePreview
from r2.tui.widgets.splitter import Splitter

MARKDOWN_SUFFIXES = {".md", ".markdown"}

IGNORED = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


def git_ignored(paths: list[Path]) -> set[Path]:
    """Return the paths that git ignores; none if git is unavailable."""
    if not paths:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=paths[0].parent,
            input="\n".join(map(str, paths)),
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {Path(line) for line in result.stdout.splitlines()}


class ProjectTree(DirectoryTree):
    def on_mount(self) -> None:
        theme.compact(self)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Hide what git ignores, plus clutter that projects may not ignore."""
        kept = [path for path in paths if path.name not in IGNORED]
        ignored = git_ignored(kept)
        return [path for path in kept if path not in ignored]


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
    ProjectView > MarkdownPane {
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        yield ProjectTree(Path.cwd())
        yield Splitter(self.ID)
        yield FilePreview()
        yield MarkdownPane()

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.query_one(ProjectTree).path = context.root
        self._show(context.view_state.get(self.ID))

    def current_link(self) -> Link | None:
        if self.context is None:
            return None
        path = self.context.view_state.get(self.ID)
        return Link(path) if isinstance(path, Path) else None

    def drawer_forward(self) -> bool:
        """Expand a closed folder; otherwise open the file and move on."""
        tree = self.query_one(ProjectTree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return False
        if node.data.path.is_dir():
            if node.is_expanded:
                return False
            node.expand()
            return True
        tree.select_node(node)
        return False

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        if self.context is not None:
            self.context.view_state[self.ID] = event.path
        self._show(event.path)

    def _show(self, path: Path | None) -> None:
        """Render Markdown files; show the others in the file preview."""
        preview = self.query_one(FilePreview)
        pane = self.query_one(MarkdownPane)
        markdown = path is not None and path.suffix.lower() in MARKDOWN_SUFFIXES
        preview.display = not markdown
        pane.display = markdown
        if path is None or self.context is None:
            preview.show(None)
        elif markdown:
            # Clear the preview, so its excerpt toggle does not linger.
            preview.show(None)
            self.run_worker(pane.open(path), exclusive=True, group="markdown")
        else:
            preview.show(Link(path), Link(path).label(self.context.root))

    def reload(self) -> None:
        super().reload()
        pane = self.query_one(MarkdownPane)
        if pane.display:
            self.run_worker(pane.reload(), exclusive=True, group="markdown")
