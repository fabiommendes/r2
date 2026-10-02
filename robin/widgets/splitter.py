"""Draggable bar that resizes the widget on its left."""

from textual import events
from textual.message import Message
from textual.widget import Widget

MIN_WIDTH = 10


class Splitter(Widget):
    """Drag this bar to resize the sibling right before it.

    The splitter only reports the new width; whoever owns the settings
    decides whether to persist it.
    """

    DEFAULT_CSS = """
    Splitter {
        width: 1;
        height: 1fr;
        background: $panel;
    }
    Splitter:hover, Splitter.-dragging {
        background: $accent;
    }
    """

    class Resized(Message):
        def __init__(self, splitter: "Splitter", width: int) -> None:
            super().__init__()
            self.splitter = splitter
            self.width = width

    def __init__(self, key: str) -> None:
        """Key identifies this splitter in the saved settings."""
        super().__init__()
        self.key = key
        self._dragging = False

    @property
    def target(self) -> Widget:
        assert self.parent is not None
        siblings = list(self.parent.children)
        return siblings[siblings.index(self) - 1]

    def set_width(self, width: int) -> int:
        """Resize the target, keeping both sides at least MIN_WIDTH wide."""
        assert isinstance(self.parent, Widget)
        available = self.parent.size.width - 1
        if available > 2 * MIN_WIDTH:
            width = max(MIN_WIDTH, min(width, available - MIN_WIDTH))
        self.target.styles.width = width
        return width

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.add_class("-dragging")
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._dragging:
            self.set_width(event.screen_x - self.target.region.x)

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.remove_class("-dragging")
        self.release_mouse()
        width = self.set_width(event.screen_x - self.target.region.x)
        self.post_message(self.Resized(self, width))
