"""Feature designs (RFCs) kept as markdown files in the project."""

from textual.binding import Binding

from r2.core.rfcs import FORMAT, new_path, new_rfc
from r2.tui.views.threads import ThreadsView
from r2.tui.widgets.prompts import Ask


class RfcsView(ThreadsView):
    ID = "rfcs"
    TITLE = "RFCs"
    FORMAT = FORMAT

    BINDINGS = [Binding("n", "new_rfc", "New RFC")]

    def action_new_rfc(self) -> None:
        self.app.push_screen(Ask("New RFC", "", "the feature to design"), self._create)

    def _create(self, title: str | None) -> None:
        if not title or not title.strip():
            return
        rfc = new_rfc(title.strip())
        self.create(rfc, lambda folder: new_path(folder, rfc.title))
