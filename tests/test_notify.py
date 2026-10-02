import io
import json
from pathlib import Path

import pytest

from robin import notify


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path


def run_hook(monkeypatch: pytest.MonkeyPatch, stdin: str) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    with pytest.raises(SystemExit) as exit_info:
        notify.main()
    assert exit_info.value.code == 0


def test_appends_event_tagged_with_pane(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HERDR_PANE_ID", "wF:p1")
    run_hook(monkeypatch, '{"hook_event_name": "Stop"}')
    run_hook(monkeypatch, '{"hook_event_name": "Stop", "tool_response": "big"}')

    lines = (state_dir / "robin" / "events.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines]
    for event in events:
        assert isinstance(event.pop("robin_time"), float)
    assert (
        events
        == [
            {"hook_event_name": "Stop", "herdr_pane_id": "wF:p1"},
        ]
        * 2
    )


def test_invalid_payload_exits_cleanly(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_hook(monkeypatch, "not json")
    assert not (state_dir / "robin" / "events.jsonl").exists()
