"""
The ingestion path of the viewer: real files, real time, a real watcher.

`watch_reports` has no ready signal, so every test starts it through
`watching`, which writes a probe report until the watcher announces it. After
that, anything written is guaranteed to be seen.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import pytest

from r2.core.reports.model import ReviewMarks
from r2.core.reports.store import ReportStore
from r2.web.watch import WatchEvent, watch_reports
from tests.reports.repo import Repo

pytestmark = pytest.mark.anyio

PROBE = "__probe__"
TIMEOUT = 5.0
#: Comfortably longer than the watcher's batching window, for asserting that
#: nothing more arrives.
SETTLE = 0.25


@dataclass
class Watching:
    events: list[WatchEvent] = field(default_factory=list)

    def of(self, path: str) -> list[str]:
        """Kinds of the events for a path, in arrival order."""
        return [e.kind for e in self.events if e.path == path]

    async def until(
        self, predicate: Callable[[list[WatchEvent]], bool], timeout: float = TIMEOUT
    ) -> None:
        deadline = time.monotonic() + timeout
        while not predicate(self.events):
            if time.monotonic() > deadline:
                raise TimeoutError(f"condition not met in {timeout}s: {self.events}")
            await asyncio.sleep(0.01)

    async def until_seen(self, kind: str, path: str) -> None:
        await self.until(lambda events: any(_is(e, kind, path) for e in events))


def _is(event: WatchEvent, kind: str, path: str) -> bool:
    return (event.kind, event.path) == (kind, path)


@contextlib.asynccontextmanager
async def watching(
    repo: Repo, on_event: Callable[[WatchEvent], None] | None = None
) -> AsyncIterator[Watching]:
    seen = Watching()
    probed = asyncio.Event()
    probe_removed = asyncio.Event()
    stop = asyncio.Event()

    def record(event: WatchEvent) -> None:
        if event.path == PROBE:
            (probe_removed if event.kind == "report-removed" else probed).set()
            return
        seen.events.append(event)
        if on_event is not None:
            on_event(event)

    task = asyncio.create_task(watch_reports(repo.project, record, stop=stop))
    probe = repo.project.reports / f"{PROBE}.md"
    try:
        deadline = time.monotonic() + TIMEOUT
        while not probed.is_set():
            if task.done() or time.monotonic() > deadline:
                task.result()
                raise TimeoutError("the watcher never announced the probe")
            probe.parent.mkdir(exist_ok=True)
            probe.write_text(str(time.monotonic()))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(probed.wait(), 0.2)
        probe.unlink()
        await asyncio.wait_for(probe_removed.wait(), TIMEOUT)
        seen.events.clear()
        yield seen
    finally:
        stop.set()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(task, TIMEOUT)
        task.cancel()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TestReportsAndMarks:
    async def test_reports_a_new_report_by_its_path(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")

    async def test_reports_a_nested_report_with_a_posix_path(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            repo.write_report("group/auth", "body\n")
            await watch.until_seen("report", "group/auth")

    async def test_reports_a_rewrite(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            repo.write_report("auth", "one\n")
            await watch.until_seen("report", "auth")
            watch.events.clear()
            repo.write_report("auth", "two\n")
            await watch.until_seen("report", "auth")

    async def test_reports_a_deletion(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            file = repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")
            file.unlink()
            await watch.until_seen("report-removed", "auth")

    async def test_a_rewrite_done_as_replace_is_never_reported_as_removed(
        self, repo: Repo
    ) -> None:
        file = repo.write_report("auth", "one\n")
        async with watching(repo) as watch:
            staged = repo.project.reports / ".auth.md.staged"
            staged.write_text("two\n")
            os.replace(staged, file)
            await watch.until_seen("report", "auth")
            await asyncio.sleep(SETTLE)
        assert "report-removed" not in watch.of("auth")

    async def test_a_rewrite_done_as_unlink_plus_create_is_reported_as_a_report(
        self, repo: Repo
    ) -> None:
        file = repo.write_report("auth", "one\n")
        async with watching(repo) as watch:
            file.unlink()
            file.write_text("two\n")
            await watch.until_seen("report", "auth")
            await asyncio.sleep(SETTLE)
        assert watch.of("auth")[-1] == "report"

    async def test_reports_marks_separately_from_the_report(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            repo.write_file(".reportlab/reports/auth.review.json", '{"findings":{}}')
            await watch.until_seen("marks", "auth")
            await asyncio.sleep(SETTLE)
        assert watch.of("auth") == ["marks"]

    async def test_reports_marks_written_by_the_store(self, repo: Repo) -> None:
        repo.write_report("group/auth", "body\n")
        async with watching(repo) as watch:
            ReportStore(repo.project).write_marks(
                "group/auth", ReviewMarks(read="2026-09-30T15:00:00Z")
            )
            await watch.until_seen("marks", "group/auth")
            await asyncio.sleep(SETTLE)
        # The store writes through a hidden temporary file, which is not a report.
        assert {e.path for e in watch.events} == {"group/auth"}


class TestWhatIsIgnored:
    async def test_ignores_files_that_are_not_reports(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            repo.write_file(".reportlab/reports/notes.txt", "x")
            repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")
        assert {e.path for e in watch.events} == {"auth"}

    async def test_ignores_hidden_files_and_folders(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            repo.write_report(".draft", "x\n")
            repo.write_report(".hidden/inner", "x\n")
            repo.write_file(".reportlab/reports/.a.review.json.tmp", "{}")
            repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")
        assert {e.path for e in watch.events} == {"auth"}

    async def test_ignores_changes_in_reportlab_outside_reports(
        self, repo: Repo
    ) -> None:
        async with watching(repo) as watch:
            (repo.project.reportlab / "config.toml").write_text("[rl]\nname = 'x'\n")
            repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")
        assert {e.path for e in watch.events} == {"auth"}

    async def test_ignores_changes_in_the_rest_of_the_repository(
        self, repo: Repo
    ) -> None:
        async with watching(repo) as watch:
            repo.write_file("src/a.py", "x = 1\n")
            repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")
        assert {e.path for e in watch.events} == {"auth"}


class TestBursts:
    async def test_coalesces_a_burst_of_writes_into_one_event(self, repo: Repo) -> None:
        async with watching(repo) as watch:
            for i in range(12):
                repo.write_report("live", f"line {i}\n")
            await watch.until(lambda events: len(events) > 0)
            await asyncio.sleep(SETTLE)
        assert watch.of("live") == ["report"]

    async def test_announces_the_last_write_of_an_agent_streaming_a_report(
        self, repo: Repo
    ) -> None:
        """
        Many writes about 40 ms apart, so each lands inside the previous
        batch's window. A reader that re-reads on every event must end up
        with the final text.
        """
        file = repo.project.reports / "live.md"
        file.write_text("line 0\n")
        final = "line 29\n"
        read_after_event: list[str] = []

        def on_event(event: WatchEvent) -> None:
            if event.path == "live":
                with contextlib.suppress(OSError):
                    read_after_event.append(file.read_text())

        async with watching(repo, on_event) as watch:
            for i in range(1, 30):
                file.write_text(f"line {i}\n")
                await asyncio.sleep(0.04)
            await watch.until(lambda _: final in read_after_event)
        assert read_after_event[-1] == final

    async def test_announces_a_write_made_from_inside_the_callback(
        self, repo: Repo
    ) -> None:
        """
        The callback re-reads the report and, the first time, writes it again.
        The second write lands while the first batch is being handled and
        must still be announced and seen.
        """
        file = repo.write_report("live", "zero\n")
        seen: list[str] = []

        def on_event(event: WatchEvent) -> None:
            if event.path != "live":
                return
            with contextlib.suppress(OSError):
                seen.append(file.read_text())
            if "second\n" not in seen and len(seen) == 1:
                file.write_text("second\n")

        async with watching(repo, on_event) as watch:
            file.write_text("first\n")
            await watch.until(lambda _: "second\n" in seen)

    async def test_a_file_deleted_right_after_being_created_is_not_left_as_a_report(
        self, repo: Repo
    ) -> None:
        async with watching(repo) as watch:
            ephemeral = repo.write_report("ephemeral", "gone soon\n")
            ephemeral.unlink()
            repo.write_report("after", "still here\n")
            await watch.until_seen("report", "after")
            await asyncio.sleep(SETTLE)
        kinds = watch.of("ephemeral")
        assert "report" not in kinds
        assert set(kinds) <= {"report-removed"}

    async def test_the_watcher_survives_a_file_deleted_right_after_being_created(
        self, repo: Repo
    ) -> None:
        async with watching(repo) as watch:
            repo.write_report("ephemeral", "x\n").unlink()
            repo.write_report("later", "x\n")
            await watch.until_seen("report", "later")

    async def test_reports_a_burst_of_many_files(self, repo: Repo) -> None:
        paths = [f"file-{i:03d}" for i in range(80)]
        async with watching(repo) as watch:
            for path in paths:
                repo.write_report(path, f"# {path}\n")
            await watch.until(
                lambda events: (
                    {e.path for e in events if e.kind == "report"} >= set(paths)
                )
            )
        assert {e.path for e in watch.events} == set(paths)
        assert {e.kind for e in watch.events} == {"report"}

    async def test_reports_files_written_right_after_their_folder_is_created(
        self, repo: Repo
    ) -> None:
        paths = [f"dir-{d:02d}/file-{i:02d}" for d in range(40) for i in range(25)]
        async with watching(repo) as watch:
            for d in range(40):
                folder = repo.project.reports / f"dir-{d:02d}"
                folder.mkdir()
                for i in range(25):
                    (folder / f"file-{i:02d}.md").write_text("x\n")
            await watch.until(
                lambda events: {e.path for e in events} >= set(paths), timeout=2.0
            )

    async def test_reports_each_path_once_for_a_burst_of_many_files(
        self, repo: Repo
    ) -> None:
        paths = [f"file-{i:03d}" for i in range(40)]
        async with watching(repo) as watch:
            for path in paths:
                repo.write_report(path, "one\n")
                repo.write_report(path, "two\n")
            await watch.until(
                lambda events: len({e.path for e in events}) == len(paths)
            )
            await asyncio.sleep(SETTLE)
        assert sorted(e.path for e in watch.events) == paths


class TestLifetime:
    async def test_stops_when_the_stop_event_is_set(self, repo: Repo) -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(
            watch_reports(repo.project, lambda _: None, stop=stop)
        )
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(task, TIMEOUT)

    async def test_stops_when_cancelled(self, repo: Repo) -> None:
        task = asyncio.create_task(watch_reports(repo.project, lambda _: None))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    async def test_watches_a_reports_folder_that_does_not_exist_yet(
        self, repo: Repo
    ) -> None:
        repo.project.reports.rmdir()
        async with watching(repo) as watch:
            repo.write_report("auth", "body\n")
            await watch.until_seen("report", "auth")
