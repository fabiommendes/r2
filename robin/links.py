"""File references collected from Claude sessions."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Paths with an extension, optionally followed by ":line" or ":start-end".
# The lookbehind skips matches inside URLs and longer tokens.
LINK_RE = re.compile(
    r"(?<![\w/.:~-])"
    r"(?P<path>(?:\.{0,2}/)?(?:[\w.-]+/)*[\w-][\w.-]*\.[A-Za-z0-9]+)"
    r"(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?"
)


@dataclass(frozen=True)
class Link:
    """A file, optionally narrowed to a range of lines (1-based, inclusive)."""

    path: Path
    start: int | None = None
    end: int | None = None

    def label(self, root: Path) -> str:
        """Render the link as Claude writes it, relative to the project root."""
        path = (
            self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        )
        if self.start is None:
            return str(path)
        if self.end is None or self.end == self.start:
            return f"{path}:{self.start}"
        return f"{path}:{self.start}-{self.end}"


def extract_links(text: str, root: Path) -> list[Link]:
    """Find references to existing files in text, in order and without repeats."""
    links: dict[Link, None] = {}
    for match in LINK_RE.finditer(text):
        path = (root / match["path"]).resolve()
        if not path.is_file():
            continue
        start = int(match["start"]) if match["start"] else None
        end = int(match["end"]) if match["end"] else start
        links[Link(path, start, end)] = None
    return list(links)


def link_from_read(tool_input: dict[str, Any]) -> Link | None:
    """Build a link from the input of Claude's Read tool."""
    file_path = tool_input.get("file_path")
    if not file_path:
        return None
    offset = tool_input.get("offset")
    limit = tool_input.get("limit")
    if offset is None and limit is None:
        return Link(Path(file_path))
    start = offset or 1
    end = start + limit - 1 if limit else None
    return Link(Path(file_path), start, end)
