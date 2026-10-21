"""
Detection of things in prose that look like references.

Phase one of two. This module is pure: it finds candidates and never decides
whether they are real, because deciding requires reading the repository. The
server resolves each candidate against the working tree; an unresolved
candidate renders as plain text.

That split is what lets detection be generous. A false positive costs a failed
tree lookup, not a broken link in the page.

The patterns use `re.ASCII` so `\\w` and `\\d` mean what they mean in the
TypeScript original. Offsets are code point indices, where the original counts
UTF-16 units; they only differ after a character outside the BMP, and every
caller slices the same Python string.
"""

from __future__ import annotations

import re

from r2.core.reports.model import Candidate

__all__ = ["candidate_key", "detect_candidates"]

#: A path with an extension, optionally followed by a locator.
#:
#: The locator forms are the ripgrep ones (`:40`, `:40:7`, `:10-40`), which is
#: what compilers, linters and editors print and therefore what an agent echoes
#: without thinking about it, plus the older `#L10-40`, which earlier versions of
#: the contract asked for (dev/adr/0012-ripgrep-style-locators.md).
_PATH = re.compile(
    r"(?<![\w/@:.-])"
    r"((?:[\w.-]+/)+[\w.-]*[\w-]\.[A-Za-z]\w{0,9}|[\w-]+\.[A-Za-z]\w{0,9})"
    r"(?::(\d+)(?:-L?(\d+)|:(\d+))?|#L(\d+)(?:-L?(\d+))?)?",
    re.ASCII,
)

#: A short or full hash. Must contain a hex letter, or it is just a number.
_COMMIT = re.compile(
    r"(?<![\w-])(?=[0-9a-f]*[a-f])([0-9a-f]{7,40})(?![\w-])",
    re.ASCII,
)


def detect_candidates(text: str) -> list[Candidate]:
    """
    Find every candidate in a run of plain text. Offsets are into `text`.

    Callers must not pass code spans, code blocks or link destinations: a path
    inside `` `foo/bar.ts` `` is already marked up, and a URL is linkified
    before this runs.
    """
    found: list[Candidate] = []

    for match in _PATH.finditer(text):
        if _overlaps(found, match.start(), match.end()):
            continue
        start_text = match[2] if match[2] is not None else match[5]
        end_text = match[3] if match[3] is not None else match[6]
        start_line: int | None = None
        end_line: int | None = None
        column: int | None = None
        if start_text is not None:
            start_line = int(start_text)
            if end_text is not None and int(end_text) > start_line:
                end_line = int(end_text)
            if match[4] is not None:
                column = int(match[4])
        found.append(
            Candidate(
                kind="path",
                raw=match[0],
                start=match.start(),
                end=match.end(),
                path=match[1],
                start_line=start_line,
                end_line=end_line,
                column=column,
            )
        )

    for match in _COMMIT.finditer(text):
        if _overlaps(found, match.start(1), match.end(1)):
            continue
        found.append(
            Candidate(
                kind="commit",
                raw=match[1],
                start=match.start(1),
                end=match.end(1),
            )
        )

    return sorted(found, key=lambda candidate: candidate.start)


def _overlaps(found: list[Candidate], start: int, end: int) -> bool:
    return any(start < c.end and end > c.start for c in found)


def candidate_key(candidate: Candidate) -> str:
    """Key used to deduplicate candidates before resolving them."""
    return f"{candidate.kind}:{candidate.raw}"
