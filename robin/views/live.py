"""Links mentioned by Claude, with a preview of each one."""

from textual.app import ComposeResult
from textual.widgets import OptionList

from robin.project import ProjectContext
from robin.views.base import View
from robin.widgets.preview import FilePreview


class LiveView(View):
    ID = "live"
    TITLE = "Live"

    DEFAULT_CSS = """
    LiveView > OptionList {
        width: 2fr;
        height: 1fr;
    }
    LiveView > FilePreview {
        width: 3fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield OptionList()
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
        options.add_options(
            link.label(self.context.root) for link in self.context.links
        )
        if self.context.links:
            links = self.context.links
            options.highlighted = links.index(selected) if selected in links else 0
        else:
            self.query_one(FilePreview).show(None)

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if self.context is None:
            return
        link = self.context.links[event.option_index]
        self.context.view_state[self.ID] = link
        self.query_one(FilePreview).show(link, link.label(self.context.root))
