"""Parsing of the info string of an `rl:` fenced block."""

from __future__ import annotations

import re

from r2.core.reports.model import BlockTag

__all__ = ["BlockTagError", "parse_block_tag"]

_TAG = re.compile(r"rl:(?P<type>[a-z][a-z0-9-]*)(?P<rest>\s.*)?")
# `\w` spelled out: it is ASCII-only in the TypeScript original, Unicode in Python.
_ATTR = re.compile(
    r'(?P<key>[a-zA-Z][A-Za-z0-9_-]*)=(?:"(?P<quoted>[^"]*)"|(?P<bare>\S+))'
)


class BlockTagError(ValueError):
    """An `rl:` fence whose tag cannot be read."""


def parse_block_tag(info: str) -> BlockTag | None:
    """
    Parse the info string of a fenced block, for example
    `rl:finding severity=high caption="Latency by endpoint"`.

    Returns `None` for a fence that is not an `rl:` block, so callers can leave
    ordinary code blocks alone.

    Raises:
        BlockTagError: The info string starts with `rl:` but is malformed.
    """
    text = info.strip()
    if not text.startswith("rl:"):
        return None

    match = _TAG.fullmatch(text)
    if match is None:
        raise BlockTagError(f"malformed block tag: {info}")

    attrs: dict[str, str] = {}
    for attr in _ATTR.finditer(match["rest"] or ""):
        quoted = attr["quoted"]
        attrs[attr["key"]] = quoted if quoted is not None else (attr["bare"] or "")
    return BlockTag(type=match["type"], attrs=attrs)
