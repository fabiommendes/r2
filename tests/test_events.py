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
