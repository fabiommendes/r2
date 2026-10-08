import asyncio
from pathlib import Path
from typing import Any

from r2.integrations.claude.events import tail


def test_tail_replays_and_follows(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"n": 1}\nbroken\n{"n": 2')

    async def collect() -> list[dict[str, Any]]:
        events = tail(path, poll=0.01)
        received = [await anext(events)]
        with path.open("a") as file:
            file.write('}\n{"n": 3}\n')
        received += [await anext(events), await anext(events)]
        return received

    assert asyncio.run(collect()) == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_recent_events_keeps_the_last_50_of_48_hours(tmp_path: Path) -> None:
    import json

    from r2.integrations.claude.events import recent_events

    now = 1_000_000.0
    old = [{"n": n, "r2_time": now - 49 * 3600} for n in range(5)]
    new = [{"n": n, "r2_time": now - 60} for n in range(5, 65)]
    path = tmp_path / "events.jsonl"
    text = "".join(json.dumps(e) + "\n" for e in old + new) + '{"partial'
    path.write_text(text)

    events, position = recent_events(path, now=now)

    assert [e["n"] for e in events] == list(range(15, 65))
    assert position == len(text) - len('{"partial')


def test_recent_events_drops_old_events_below_the_count(tmp_path: Path) -> None:
    from r2.integrations.claude.events import recent_events

    path = tmp_path / "events.jsonl"
    path.write_text('{"n": 1, "r2_time": 0}\n{"n": 2, "r2_time": 999999}\n')
    assert recent_events(path, now=1_000_000)[0] == [{"n": 2, "r2_time": 999999}]


def test_tail_starts_at_the_position(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"n": 1}\n{"n": 2}\n')

    async def first() -> dict[str, Any]:
        return await anext(tail(path, poll=0.01, position=9))

    assert asyncio.run(first()) == {"n": 2}


def test_append_event_rotates_a_big_log(tmp_path: Path) -> None:
    from r2.integrations.claude import notify

    path = tmp_path / "events.jsonl"
    path.write_text("x" * 100)
    notify.rotate(path, max_size=50)
    notify.append_event({"n": 1}, path)

    assert (tmp_path / "events.jsonl.1").read_text() == "x" * 100
    assert path.read_text() == '{"n": 1}\n'
