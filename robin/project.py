"""Per-project state.

Herdr focus can move between projects at any time, so robin keeps one context
per project and switches between them instead of resetting its views.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from robin.links import Link

MAX_LINKS = 200


def find_root(path: Path) -> Path:
    """Return the git root that contains path, or path itself."""
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return path


@dataclass
class ProjectContext:
    """Everything robin knows about one project."""

    root: Path
    links: list[Link] = field(default_factory=list)
    view_state: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.root.name

    def add_links(self, links: list[Link]) -> None:
        """Put links at the top of the list, moving the ones already seen."""
        seen = set(links)
        self.links = links + [link for link in self.links if link not in seen]
        del self.links[MAX_LINKS:]


class Projects:
    """Project contexts indexed by root directory."""

    def __init__(self) -> None:
        self._contexts: dict[Path, ProjectContext] = {}

    def get(self, path: Path) -> ProjectContext:
        """Return the context of the project that contains path."""
        root = find_root(path.resolve())
        if root not in self._contexts:
            self._contexts[root] = ProjectContext(root)
        return self._contexts[root]
