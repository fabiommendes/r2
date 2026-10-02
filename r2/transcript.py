"""Read Claude Code transcripts."""

import json
from pathlib import Path
from typing import Any


def _is_prompt(entry: dict[str, Any]) -> bool:
    """Tell prompts typed by the user from tool results, also stored as user entries."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = entry["message"]["content"]
    if isinstance(content, str):
        return True
    return any(block.get("type") == "text" for block in content)


def last_turn_text(path: Path) -> str:
    """Return the text Claude wrote since the last prompt."""
    entries = [json.loads(line) for line in path.read_text().splitlines() if line]
    texts: list[str] = []
    for entry in reversed(entries):
        if _is_prompt(entry):
            break
        if entry.get("type") == "assistant" and not entry.get("isSidechain"):
            for block in reversed(entry["message"]["content"]):
                if block.get("type") == "text":
                    texts.append(block["text"])
    return "\n".join(reversed(texts))
