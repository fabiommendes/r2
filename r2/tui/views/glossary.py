"""The project's glossary, one term at a time."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, Markdown, Static, Tree
from textual.widgets.tree import TreeNode

from r2.core.files import update
from r2.core.glossary import FILE, Glossary, Term, parse, term_line
from r2.core.links import Link
from r2.core.r2_context import ProjectContext
from r2.tui import theme
from r2.tui.views.base import View
from r2.tui.widgets.meta import SEPARATOR, FieldRenderer, MetaBar, clickable
from r2.tui.widgets.prompts import Ask
from r2.tui.widgets.splitter import Splitter

UNTAGGED = "untagged"

LINK_MARK = " ↗"


def related_terms(glossary: Callable[[], Glossary]) -> FieldRenderer:
    """Render related entries as links to the terms they name.

    Entries that name no term show dim.
    """

    def render(value: Any, colors: dict[str, str]) -> Text:
        text = Text()
        for index, name in enumerate(str(value).split(",")):
            name = name.strip()
            if index:
                text.append(SEPARATOR, style="dim")
            if glossary().find(name) is None:
                text.append(name, style="dim")
                continue
            link = Text(name, style=f"underline {colors['text-accent']}")
            link.append(LINK_MARK, style=colors["text-accent"])
            text.append_text(clickable(link, "related", name))
        return text

    return render


def term_meta(term: Term) -> dict[str, Any]:
    """The fields of term as the meta bar shows them, lists split."""
    lists = {"tags", "avoid"}
    return {
        key: term.items(key) if key in lists else value
        for key, value in term.fields.items()
        if value
    }


def groups(glossary: Glossary, query: str) -> dict[str, list[Term]]:
    """The terms that match query, by tag, sorted.

    A term shows under each of its tags. Without any tag in the glossary,
    everything goes in one group with an empty name.
    """
    tags = glossary.tags()
    terms = sorted(
        (term for term in glossary.terms if term.matches(query)),
        key=lambda term: term.name.lower(),
    )
    if not tags:
        return {"": terms} if terms else {}
    found: dict[str, list[Term]] = {}
    for tag in [*tags, UNTAGGED]:
        key = tag.lower()
        members = [
            term
            for term in terms
            if key in {t.lower() for t in term.tags}
            or (tag == UNTAGGED and not term.tags)
        ]
        if members:
            found[tag] = members
    return found


class GlossaryView(View):
    ID = "glossary"
    TITLE = "Glossary"

    DEFAULT_CSS = """
    GlossaryView > #drawer {
        height: 1fr;
    }
    GlossaryView #filter {
        background: $boost;
    }
    GlossaryView > #term {
        width: 1fr;
    }
    GlossaryView #empty {
        padding: 1 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("n", "new_term", "New term"),
        Binding("slash", "filter", "Filter"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.glossary = Glossary(terms=[], intro="")
        self.current: Term | None = None
        self._expanded: dict[str, bool] = {}
        """Groups the user opened or closed, by tag."""
        self._groups: dict[TreeNode[Term], str] = {}

    def compose(self) -> ComposeResult:
        tree: Tree[Term] = Tree("glossary")
        tree.show_root = False
        theme.compact(tree)
        with Vertical(id="drawer"):
            yield tree
            yield Input(id="filter", placeholder="/ filter", compact=True)
        yield Splitter(self.ID)
        with Vertical(id="term"):
            yield MetaBar({"related": related_terms(lambda: self.glossary)})
            with VerticalScroll():
                yield Static(id="empty")
                yield Markdown()

    @property
    def path(self) -> Path | None:
        return self.context.root / FILE if self.context else None

    def set_context(self, context: ProjectContext) -> None:
        super().set_context(context)
        self.current = None
        self.reload()

    def reload(self) -> None:
        """Read the glossary file again and show the same term."""
        path = self.path
        try:
            text = path.read_text(errors="replace") if path else ""
        except OSError:
            text = ""
        self.glossary = parse(text)
        if self.current is not None:
            self.current = self.glossary.find(self.current.name)
        self.fill()
        self.show(self.current)

    def fill(self) -> None:
        tree = self.query_one(Tree)
        tree.clear()
        query = self.query_one("#filter", Input).value
        self._groups = {}
        cursor: TreeNode[Term] | None = None
        for tag, terms in groups(self.glossary, query).items():
            if tag:
                parent = tree.root.add(
                    f"{tag} [dim]{len(terms)}[/]",
                    expand=bool(query) or self._expanded.get(tag, True),
                )
                self._groups[parent] = tag
            else:
                parent = tree.root
            for term in terms:
                leaf = parent.add_leaf(term.name, data=term)
                if cursor is None and term is self.current:
                    cursor = leaf
        if cursor is not None:
            tree.call_after_refresh(tree.move_cursor, cursor)

    def show(self, term: Term | None) -> None:
        self.current = term
        empty = self.query_one("#empty", Static)
        markdown = self.query_one(Markdown)
        meta = self.query_one(MetaBar)
        if term is None:
            path = self.path
            if path is None or not path.is_file():
                empty.update(f"No {FILE} in this project. Press n to add a term.")
            else:
                empty.update(self.glossary.intro or "Pick a term on the left.")
            empty.display = True
            markdown.display = False
            meta.show(None)
            return
        empty.display = False
        markdown.display = True
        meta.show(term_meta(term))
        markdown.update(f"# {term.name}\n\n{term.definition}")

    def select(self, name: str) -> None:
        """Show the term called name and move the tree cursor to it."""
        term = self.glossary.find(name)
        if term is None:
            return
        self.show(term)
        self.fill()
        self.post_message(self.Navigated())

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[Term]) -> None:
        if event.node.data is not None:
            self.show(event.node.data)

    def on_tree_node_selected(self, event: Tree.NodeSelected[Term]) -> None:
        if event.node.data is not None:
            self.post_message(self.Navigated())

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[Term]) -> None:
        if tag := self._groups.get(event.node):
            self._expanded[tag] = True

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed[Term]) -> None:
        if tag := self._groups.get(event.node):
            self._expanded[tag] = False

    def on_meta_bar_field_clicked(self, event: MetaBar.FieldClicked) -> None:
        if event.key == "related":
            event.stop()
            self.select(event.value)

    def action_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.fill()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one(Tree).focus()

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and isinstance(self.app.focused, Input):
            self.query_one(Tree).focus()
            event.stop()

    def shows(self, path: Path) -> bool:
        return self.path is not None and path == self.path

    async def show_file(self, path: Path) -> None:
        self.reload()

    def current_link(self) -> Link | None:
        path = self.path
        if path is None or not path.is_file():
            return None
        if self.current is None:
            return Link(path)
        try:
            line = term_line(path.read_text(errors="replace"), self.current.name)
        except OSError:
            line = None
        return Link(path, line)

    def action_new_term(self) -> None:
        self.app.push_screen(Ask("New term", "", "the word to define"), self._create)

    def _create(self, name: str | None) -> None:
        path = self.path
        name = (name or "").strip()
        if path is None or not name:
            return
        exists = False

        def add(text: str) -> str:
            nonlocal exists
            glossary = parse(text)
            if glossary.find(name) is not None:
                exists = True
                return text
            glossary.terms.append(Term(name))
            return glossary.sorted().to_markdown()

        try:
            text = update(path, add)
        except OSError as error:
            self.notify(f"Could not write {FILE}: {error}", severity="error")
            return
        if exists:
            self.notify(f"{name!r} is already in the glossary", severity="warning")
            self.reload()
            self.select(name)
            return
        self.reload()
        self.select(name)
        line = term_line(text, name)
        self.post_message(self.EditFile(Link(path, line + 2 if line else None)))
