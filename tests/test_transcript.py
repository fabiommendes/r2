import json
from pathlib import Path

from r2.integrations.claude.transcript import last_turn_text


def entry(kind: str, content: object) -> str:
    return json.dumps({"type": kind, "message": {"content": content}})


def test_collects_text_since_last_prompt(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    lines = [
        entry("user", "first prompt"),
        entry("assistant", [{"type": "text", "text": "old answer"}]),
        entry("user", "second prompt"),
        entry("assistant", [{"type": "thinking", "thinking": "hm"}]),
        entry("assistant", [{"type": "text", "text": "part one"}]),
        entry("user", [{"type": "tool_result", "content": "ok"}]),
        entry("assistant", [{"type": "text", "text": "part two"}]),
    ]
    path.write_text("\n".join(lines) + "\n")
    assert last_turn_text(path) == "part one\npart two"
