"""
The working tree, as the report viewer reads it.

This is the only module that reads arbitrary paths out of a project, and
every path that arrives from an HTTP request or from a report reference goes
through `confine`. The viewer serves file contents to a browser, so an escape
here reads the user's whole filesystem.

The API is coarse on purpose: one call per whole file or whole tree, data in
and data out, so a native helper can replace parts of it later without a
chatty boundary in between.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from stat import S_ISREG
from typing import Literal

__all__ = [
    "FileStat",
    "ReadFailure",
    "SourceFile",
    "confine",
    "language_of",
    "list_source_files",
    "read_source_file",
    "stat_files",
]

#: Past this, a file is cut at a line boundary. A browser cannot use more.
MAX_BYTES = 2 * 1024 * 1024

#: How much of the head is checked for a NUL byte before calling it binary.
SNIFF = 8 * 1024

SKIP_DIRS = frozenset(
    {".git", ".reportlab", "node_modules", "dist", "build", "coverage"}
)


@dataclass(frozen=True)
class FileStat:
    #: Project-relative path, exactly as it was asked for.
    path: str
    modified: datetime
    size: int


@dataclass(frozen=True)
class SourceFile(FileStat):
    #: sha256 of the bytes that were read.
    hash: str
    #: One entry per line, so the UI numbers rows without splitting again.
    lines: list[str]
    #: Shiki language id, from the extension. None means no grammar for it.
    lang: str | None = None
    #: The file was longer than the cap and `lines` stops early.
    truncated: bool = False


#: Why a file could not be read. A path that escapes the project is
#: `missing`: the viewer does not confirm the existence of anything outside.
type ReadFailure = Literal["missing", "binary"]


def confine(root: Path, candidate: str) -> Path | None:
    """
    Resolve candidate inside root, or return None if it escapes.

    Symlinks are followed before the check, and a path that does not exist
    yet is checked against its nearest existing ancestor. There is one copy
    of this check on purpose: a second one is a second thing to get right.
    """
    if "\0" in candidate:
        return None
    target = Path(os.path.normpath(root / candidate))
    try:
        real = target.resolve(strict=True)
    except (OSError, RuntimeError):
        # resolve(strict=False) resolves the longest existing prefix.
        parent = target.parent.resolve()
        if not _within(root, parent):
            return None
        return target if _within(root, target) else None
    return real if _within(root, real) else None


def _within(root: Path, path: Path) -> bool:
    return path == root or path.is_relative_to(root)


def list_source_files(root: Path) -> list[FileStat]:
    """Files in the working tree, excluding tool and dependency folders."""
    found: list[FileStat] = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        base = Path(folder)
        prefix = base.relative_to(root).as_posix()
        for name in files:
            path = base / name
            try:
                stat = path.lstat()
            except OSError:
                continue
            if not path.is_file() or path.is_symlink():
                continue
            relative = name if prefix == "." else f"{prefix}/{name}"
            found.append(FileStat(relative, _mtime(stat.st_mtime), stat.st_size))
    found.sort(key=lambda entry: entry.path)
    return found


def read_source_file(
    root: Path, path: str, *, max_bytes: int = MAX_BYTES
) -> SourceFile | ReadFailure:
    """Read a text file of the working tree, or say why it cannot be."""
    real = confine(root, path)
    if real is None:
        return "missing"
    try:
        with real.open("rb") as file:
            stat = os.fstat(file.fileno())
            if not S_ISREG(stat.st_mode):
                return "missing"
            data = file.read(max_bytes)
    except OSError:
        return "missing"

    text = _as_text(data)
    if text is None:
        return "binary"
    truncated = stat.st_size > len(data)
    if truncated and "\n" in text:
        text = text[: text.rindex("\n")]
    return SourceFile(
        path=path,
        modified=_mtime(stat.st_mtime),
        size=stat.st_size,
        hash=hashlib.sha256(data).hexdigest(),
        lines=_to_lines(text),
        lang=language_of(path),
        truncated=truncated,
    )


def stat_files(root: Path, paths: list[str]) -> dict[str, FileStat]:
    """
    Which of these paths are regular files inside root, in one call. This is
    what resolves a report's references.
    """
    found: dict[str, FileStat] = {}
    for path in paths:
        real = confine(root, path)
        if real is None:
            continue
        try:
            stat = real.stat()
        except OSError:
            # Not there. Absence is the answer, not an error.
            continue
        if real.is_file():
            found[path] = FileStat(path, _mtime(stat.st_mtime), stat.st_size)
    return found


def _as_text(data: bytes) -> str | None:
    """
    None when the bytes are not text.

    A NUL byte in the head is what every binary has and no text file does,
    and strict UTF-8 catches a short binary with no NUL. An incomplete
    character at the end, which a truncated read leaves behind, is dropped
    rather than refused. A text file in a legacy single-byte encoding reads
    as binary: refusing it is better than showing it wrong.
    """
    if b"\0" in data[:SNIFF]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        if error.reason != "unexpected end of data":
            return None
        return data[: error.start].decode("utf-8")


def _to_lines(text: str) -> list[str]:
    """
    One entry per line the way an editor counts them: a file ending in a
    newline has no extra empty line at the end.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return lines


def _mtime(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds).astimezone()


#: Extension to shiki language id. An unknown extension means no
#: highlighting, which is a readable file view anyway.
BY_EXTENSION = {
    ".astro": "astro",
    ".bash": "bash",
    ".c": "c",
    ".cc": "cpp",
    ".cjs": "javascript",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".css": "css",
    ".dart": "dart",
    ".diff": "diff",
    ".elm": "elm",
    ".ex": "elixir",
    ".exs": "elixir",
    ".fish": "fish",
    ".go": "go",
    ".graphql": "graphql",
    ".h": "c",
    ".hpp": "cpp",
    ".hs": "haskell",
    ".html": "html",
    ".ini": "ini",
    ".java": "java",
    ".js": "javascript",
    ".json": "json",
    ".jsonc": "jsonc",
    ".jsx": "jsx",
    ".kt": "kotlin",
    ".lua": "lua",
    ".md": "markdown",
    ".mdx": "mdx",
    ".mjs": "javascript",
    ".nix": "nix",
    ".php": "php",
    ".pl": "perl",
    ".py": "python",
    ".pyi": "python",
    ".r": "r",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".scss": "scss",
    ".sh": "bash",
    ".sql": "sql",
    ".svelte": "svelte",
    ".swift": "swift",
    ".tf": "terraform",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".vue": "vue",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".zig": "zig",
    ".zsh": "bash",
}

#: Files whose name alone is enough to know the language.
BY_NAME = {
    ".bashrc": "bash",
    ".gitignore": "ini",
    ".zshrc": "bash",
    "Dockerfile": "docker",
    "Makefile": "make",
}


def language_of(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if name in BY_NAME:
        return BY_NAME[name]
    suffix = Path(name).suffix.lower()
    return BY_EXTENSION.get(suffix)
