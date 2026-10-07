"""Text search shared by the file preview and the Markdown pane."""

from rich.markup import escape
from textual import events
from textual.message import Message
from textual.widgets import Input

Match = tuple[int, int, int]
"""A search match as row, start column and end column."""


def find_spans(text: str, pattern: str) -> list[tuple[int, int]]:
    """Start and end of every occurrence of pattern in text, in order.

    The search ignores case unless pattern has an uppercase letter.
    """
    if not pattern:
        return []
    fold = pattern == pattern.lower()
    needle = pattern.lower() if fold else pattern
    haystack = text.lower() if fold else text
    # Lower casing may change the length (İ becomes i̇), breaking offsets.
    if len(haystack) != len(text):
        haystack = text
    spans: list[tuple[int, int]] = []
    start = haystack.find(needle)
    while start >= 0:
        spans.append((start, start + len(needle)))
        start = haystack.find(needle, start + len(needle))
    return spans


def find_matches(lines: list[str], pattern: str) -> list[Match]:
    """Find every occurrence of pattern in lines, in document order."""
    return [
        (row, start, end)
        for row, line in enumerate(lines)
        for start, end in find_spans(line, pattern)
    ]


def describe(pattern: str, current: int, total: int) -> str:
    """Markup telling where the search stands, empty without a search."""
    if not pattern:
        return ""
    if not total:
        return f"/{escape(pattern)} not found"
    return f"/{escape(pattern)} {current + 1}/{total}, ↑↓ to move, esc to clear"


class SearchBar(Input):
    """One line input for a search pattern, hidden until opened.

    Enter posts Input.Submitted as usual; escape closes the bar and posts
    Cancelled. The host hides the bar after a submit with close().
    """

    DEFAULT_CSS = """
    SearchBar {
        display: none;
    }
    """

    class Cancelled(Message):
        """The bar was closed without a search."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id, placeholder="/ search", compact=True)

    def open(self) -> None:
        self.value = ""
        self.display = True
        self.focus()

    def close(self) -> None:
        self.display = False

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.close()
            self.post_message(self.Cancelled())
