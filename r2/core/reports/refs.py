"""
Parsing and formatting of refs such as `src/auth/session.py:40-58`.

Pure, with no filesystem access. It is the first of two checks on every path in
the product: this one rejects a shape, and `confine` in the scan layer rejects
a symlink that leaves the project. Neither replaces the other.

Not to be confused with `r2.core.links`, which accepts absolute paths from
Claude transcripts. A ref comes from a report, which is untrusted input.
"""

from __future__ import annotations

import re

from r2.core.reports.model import Ref

__all__ = ["RefError", "format_ref", "normalize_repo_path", "parse_ref"]

#: The locator at the end of a ref.
#:
#: The canonical form is the one ripgrep, compilers and editors print, because
#: it is the one an agent echoes without thinking about it
#: (dev/adr/0012-ripgrep-style-locators.md):
#:
#:     path:5        one line
#:     path:5:10     line and column
#:     path:5-40     a range
#:
#: The GitHub form `path#L5-40` is still read, so a report written against an
#: older version of the contract keeps working. It is not what `format_ref`
#: emits. ASCII digits only, as in the TypeScript original.
_LOCATOR = re.compile(
    r"(?::(\d+)(?:-L?(\d+)|:(\d+))?|#L(\d+)(?:-L?(\d+))?)\Z",
    re.ASCII,
)
_WINDOWS_ABSOLUTE = re.compile(r"[a-zA-Z]:[\\/]")


class RefError(ValueError):
    """The ref is malformed or points outside the repository."""


def parse_ref(raw: str) -> Ref:
    """
    Parse a ref such as `src/auth/session.py:40-58`.

    Rejects absolute paths, `..` segments and inverted ranges here, in a module
    with no filesystem access, so that nothing downstream has to remember to.

    Raises:
        RefError: The ref is empty, escapes the repository or has a bad locator.
    """
    text = raw.strip()
    if text == "":
        raise RefError("empty ref")

    match = _LOCATOR.search(text)
    path = normalize_repo_path(text if match is None else text[: match.start()])
    if path is None:
        raise RefError(f"ref must stay inside the repository: {raw}")
    if path == "":
        raise RefError(f"ref has no path: {raw}")
    if match is None:
        return Ref(path=path)

    line, range_end, column, hash_line, hash_end = match.groups()
    start_text = line if line is not None else hash_line
    if start_text is None:
        return Ref(path=path)

    start = int(start_text)
    if start < 1:
        raise RefError(f"line numbers are 1-based: {raw}")

    end: int | None = None
    end_text = range_end if range_end is not None else hash_end
    if end_text is not None:
        end_line = int(end_text)
        if end_line < start:
            raise RefError(f"inverted line range: {raw}")
        if end_line != start:
            end = end_line

    column_number: int | None = None
    if column is not None:
        column_number = int(column)
        if column_number < 1:
            raise RefError(f"columns are 1-based: {raw}")

    return Ref(path=path, start=start, end=end, column=column_number)


def normalize_repo_path(raw: str) -> str | None:
    """Return a repository-relative path, or `None` if it escapes the root."""
    if raw.startswith("/") or _WINDOWS_ABSOLUTE.match(raw):
        return None
    if "\0" in raw:
        return None

    parts: list[str] = []
    for part in raw.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    return "/".join(parts)


def format_ref(ref: Ref) -> str:
    """The canonical form, which is the one a human can paste into an editor."""
    if ref.start is None:
        return ref.path
    if ref.end is not None and ref.end != ref.start:
        return f"{ref.path}:{ref.start}-{ref.end}"
    if ref.column is not None:
        return f"{ref.path}:{ref.start}:{ref.column}"
    return f"{ref.path}:{ref.start}"
