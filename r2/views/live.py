"""Links mentioned by Claude, with a preview of each one."""

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import OptionList

from r2.links import Link
from r2.project import ProjectContext
from r2.views.base import View
from r2.widgets.preview import FilePreview
from r2.widgets.splitter import Splitter


class LiveView(View):
    ID = "live"
    TITLE = "Live"

    DEFAULT_CSS = """
    LiveView > OptionList {
        height: 1fr;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    LiveView > FilePreview {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield OptionList()
        yield Splitter(self.ID)
        yield FilePreview()

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.links_changed()

    def links_changed(self) -> None:
        if self.context is None:
            return
        options = self.query_one(OptionList)
        selected = self.context.view_state.get(self.ID)
        options.clear_options()
        options.add_options(self._prompt(link) for link in self.context.links)
        if self.context.links:
            links = self.context.links
            options.highlighted = links.index(selected) if selected in links else 0
        else:
            self.query_one(FilePreview).show(None)

    def _prompt(self, link: Link) -> Text:
        """Show the file name first, so truncation only hides the directory."""
        assert self.context is not None
        label = Path(link.label(self.context.root))
        directory = "" if str(label.parent) == "." else f"  {label.parent}"
        return Text.assemble(label.name, (directory, "dim"))

    def current_link(self) -> Link | None:
        if self.context is None:
            return None
        link = self.context.view_state.get(self.ID)
        return link if isinstance(link, Link) else None

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if self.context is None:
            return
        link = self.context.links[event.option_index]
        self.context.view_state[self.ID] = link
        self.query_one(FilePreview).show(link, link.label(self.context.root))
