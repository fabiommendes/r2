"""
Glossary is a special markdown document with the following structure:

```markdown
# Glossary

One or more paragraphs of introduction text.

---

## Definition 1

Definition 1 text.


## Definition 2

Definition 2 text.

....

```
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["Glossary", "Term", "parse"]


@dataclass
class Term:
    name: str
    definition: str


@dataclass
class Glossary:
    terms: list[Term]
    intro: str
    title: str = "Glossary"

    def sorted(self) -> Glossary:
        """
        Sort the glossary terms alphabetically by name.
        """
        return Glossary(
            terms=sorted(self.terms, key=lambda term: term.name.lower()),
            intro=self.intro,
            title=self.title,
        )

    def render(self) -> str:
        """
        Render the glossary as a string.
        """
        output = [self.intro, ""]
        for term in self.terms:
            output.append(f"{term.name}: {term.definition}")
        return "\n".join(output)

    def to_markdown(self) -> str:
        """
        Render the glossary back as a markdown document.

        The result round-trips through :func:`parse`.
        """
        lines = [f"# {self.title}", ""]
        if self.intro:
            lines += [self.intro, ""]
        lines += ["---", ""]

        for term in self.terms:
            lines += [f"## {term.name}", ""]
            if term.definition:
                lines += [term.definition, ""]

        return "\n".join(lines)


def parse(src: str) -> Glossary:
    """
    Parse a glossary from a string.
    """
    parser = GlossaryParser(src)
    doc = parser.parse()
    if parser.is_empty():
        return doc
    raise ValueError("Unexpected content after glossary document.")


class GlossaryParser:
    """
    A parser for glossary files.
    """

    def __init__(self, src: str):
        self.src = src
        self.lines = deque(src.splitlines())

        self.intro = ""
        self.title = "Glossary"
        self.terms: list[Term] = []

    def parse(self) -> Glossary:
        """
        Parse the glossary file.
        """

        self.title = self.parse_title()
        self.intro = self.parse_intro()

        while self.lines:
            term = self.parse_term()
            self.terms.append(term)

        return Glossary(terms=self.terms.copy(), intro=self.intro, title=self.title)

    def is_empty(self) -> bool:
        return not self.lines

    def read(self) -> str:
        if not self.lines:
            return ""
        return self.lines.popleft()

    def peek(self) -> str:
        if not self.lines:
            return ""
        return self.lines[0]

    def read_if(self, pred: Callable[[str], bool]) -> str | None:
        if not self.lines:
            return None

        if pred(self.peek()):
            return self.lines.popleft()
        return None

    def match(self, pred: Callable[[str], bool] | str) -> str | None:
        pred = normalize_pred(pred)
        if not self.lines:
            return None
        if pred(self.peek()):
            return self.lines.popleft()
        return None

    def expect(self, pred: Callable[[str], bool] | str) -> str:
        pred = normalize_pred(pred)
        if not self.lines:
            raise ValueError("Unexpected end of input.")
        line = self.lines.popleft()
        if not pred(line):
            raise ValueError(f"Unexpected line: {line}")
        return line

    def expect_prefix(self, prefix: str) -> None:
        if not self.lines:
            message = f"Expect a line starting with {prefix!r}, but got end of input."
            raise ValueError(message)

        if not self.lines[0].startswith(prefix):
            msg = f"Expect a line starting with {prefix!r}, but got: {self.lines[0]!r}"
            raise ValueError(msg)

        self.lines[0] = self.lines[0].removeprefix(prefix)

    def consume_ws(self) -> None:
        """
        Remove any empty lines.
        """
        while self.read_if(lambda line: not line.strip()) is not None:
            pass

    #
    # Parse elements of the glossary
    #
    def parse_title(self) -> str:
        """
        Title is of the form `# Glossary [optional subtitle]`
        """
        self.consume_ws()
        self.expect_prefix("# ")
        title = self.expect(lambda line: line.strip().lower().startswith("glossary"))
        return title.strip()

    def parse_intro(self) -> str:
        """
        Parse the introduction text.

        Those are arbitrary paragraphs of text before the first `---` line.
        """
        self.consume_ws()
        intro_lines = []

        while self.lines and not self.match("---"):
            intro_lines.append(self.read())

        return "\n".join(intro_lines).rstrip()

    def parse_term(self) -> Term:
        """
        Parse a term definition.

        A term definition is of the form:

        ```
        ## Term Name

        Definition text.
        ```
        """
        self.consume_ws()
        self.expect_prefix("## ")
        name = self.read().strip()

        self.consume_ws()
        definition_lines = []

        while self.lines and not self.peek().startswith("## "):
            definition_lines.append(self.read())

        return Term(name=name, definition="\n".join(definition_lines).rstrip())


def normalize_pred(pred: Callable[[str], bool] | str) -> Callable[[str], bool]:
    if isinstance(pred, str):
        return lambda line: line.rstrip() == pred
    return pred
