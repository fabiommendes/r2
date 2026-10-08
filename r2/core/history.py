"""Navigation history across the views, like a browser's."""

from dataclasses import dataclass

from r2.core.links import Link

MAX_ENTRIES = 100


@dataclass(frozen=True)
class Location:
    """A view (tab id) and the file that has the focus there, if any."""

    view: str
    link: Link | None = None


class History:
    """Locations visited, with a cursor to go back and forward."""

    def __init__(self, limit: int = MAX_ENTRIES) -> None:
        self.limit = limit
        self._entries: list[Location] = []
        self._index = -1

    @property
    def current(self) -> Location | None:
        return self._entries[self._index] if self._entries else None

    @property
    def can_go_back(self) -> bool:
        return self._index > 0

    @property
    def can_go_forward(self) -> bool:
        return self._index < len(self._entries) - 1

    def visit(self, location: Location) -> None:
        """Make location the current one and forget what was ahead of it."""
        if location == self.current:
            return
        del self._entries[self._index + 1 :]
        self._entries.append(location)
        del self._entries[: -self.limit]
        self._index = len(self._entries) - 1

    def back(self) -> Location | None:
        """Step back; return the new current location, or None at the start."""
        if not self.can_go_back:
            return None
        self._index -= 1
        return self._entries[self._index]

    def forward(self) -> Location | None:
        """Step forward; return the new current location, or None at the end."""
        if not self.can_go_forward:
            return None
        self._index += 1
        return self._entries[self._index]
