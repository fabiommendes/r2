"""
The daemon end to end: `r2 web serve` as a real process on a real port, with
the registry, the watcher and the event stream wired together.
"""

from __future__ import annotations

import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

from r2.web.daemon import serve
from r2.web.registry import register
from r2.web.state import BIND_ADDRESS, DaemonState, read_live_daemon_state
from tests.reports.repo import Repo

STARTUP = 20.0


class Daemon:
    def __init__(self, process: subprocess.Popen[str], state: DaemonState) -> None:
        self.process = process
        self.state = state

    @property
    def url(self) -> str:
        return f"http://{BIND_ADDRESS}:{self.state.port}"

    @property
    def auth(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.state.token}"}

    def get(self, path: str, **options: Any) -> httpx.Response:
        headers = {**self.auth, **options.pop("headers", {})}
        return httpx.get(self.url + path, headers=headers, timeout=5, **options)


def free_port() -> int:
    with closing(socket.socket()) as sock:
        sock.bind((BIND_ADDRESS, 0))
        port: int = sock.getsockname()[1]
        return port


def spawn(port: int) -> subprocess.Popen[str]:
    """`r2 web serve`, inheriting the test's isolated state and config."""
    return subprocess.Popen(
        [sys.executable, "-m", "r2", "web", "serve", "--port", str(port)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "R2_WEB_STATIC": ""},
    )


def wait_for_daemon(process: subprocess.Popen[str]) -> DaemonState:
    deadline = time.monotonic() + STARTUP
    while time.monotonic() < deadline:
        if process.poll() is not None:
            out = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"the daemon exited early: {out}")
        state = read_live_daemon_state()
        if state is not None and state.pid == process.pid:
            try:
                httpx.get(
                    f"http://{BIND_ADDRESS}:{state.port}/api/health",
                    headers={"authorization": f"Bearer {state.token}"},
                    timeout=1,
                ).raise_for_status()
            except httpx.HTTPError:
                pass
            else:
                return state
        time.sleep(0.05)
    process.kill()
    raise TimeoutError("the daemon did not come up")


def terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    if process.stdout:
        process.stdout.close()


@pytest.fixture
def start_daemon() -> Iterator[Callable[[int], Daemon]]:
    started: list[subprocess.Popen[str]] = []

    def start(port: int = 0) -> Daemon:
        process = spawn(port or free_port())
        started.append(process)
        return Daemon(process, wait_for_daemon(process))

    yield start
    for process in started:
        # Not a graceful stop: that waits for every open event stream.
        process.kill()
        process.wait()
        if process.stdout:
            process.stdout.close()


@pytest.fixture
def daemon(repo: Repo, start_daemon: Callable[[int], Daemon]) -> Daemon:
    register(repo.project)
    return start_daemon(0)


class EventStream:
    """Server-sent events read on a thread, so a test can wait with a timeout."""

    def __init__(self, daemon: Daemon, project: str) -> None:
        self.frames: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.status = 0
        self.content_type = ""
        self.ready = threading.Event()
        self.thread = threading.Thread(
            target=self._read, args=(daemon, project), daemon=True
        )
        self.thread.start()

    def _read(self, daemon: Daemon, project: str) -> None:
        url = f"{daemon.url}/api/p/{project}/stream"
        try:
            with httpx.stream(
                "GET", url, headers=daemon.auth, timeout=httpx.Timeout(30)
            ) as response:
                self.status = response.status_code
                self.content_type = response.headers.get("content-type", "")
                self.ready.set()
                name = ""
                for line in response.iter_lines():
                    if line.startswith("event:"):
                        name = line.removeprefix("event:").strip()
                    elif line.startswith("data:") and name:
                        data = json.loads(line.removeprefix("data:").strip())
                        self.frames.put((name, data))
        except httpx.HTTPError:
            pass
        finally:
            self.ready.set()

    def next_event(self, name: str, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"no {name!r} event within {timeout}s")
            try:
                got, data = self.frames.get(timeout=remaining)
            except queue.Empty:
                continue
            if got == name:
                return data


@contextmanager
def event_stream(daemon: Daemon, project: str) -> Iterator[EventStream]:
    stream = EventStream(daemon, project)
    assert stream.ready.wait(5)
    yield stream


class TestServe:
    def test_binds_loopback_on_the_requested_port(self, daemon: Daemon) -> None:
        response = daemon.get("/api/health")
        assert response.json() == {"ok": True, "projects": 1}
        assert daemon.state.pid == daemon.process.pid
        with closing(socket.socket()) as probe:
            assert probe.connect_ex((BIND_ADDRESS, daemon.state.port)) == 0

    def test_serves_the_projects_in_the_registry(
        self, daemon: Daemon, repo: Repo
    ) -> None:
        [project] = daemon.get("/api/projects").json()
        assert project["id"] == repo.project.id

    def test_refuses_an_unauthenticated_request(self, daemon: Daemon) -> None:
        response = httpx.get(f"{daemon.url}/api/health")
        assert response.status_code == 401

    def test_falls_back_to_another_port_when_the_preferred_one_is_taken(
        self, repo: Repo, start_daemon: Callable[[int], Daemon]
    ) -> None:
        register(repo.project)
        with closing(socket.socket()) as taken:
            taken.bind((BIND_ADDRESS, 0))
            taken.listen()
            busy = taken.getsockname()[1]
            running = start_daemon(busy)
            assert running.state.port != busy
            assert running.get("/api/health").status_code == 200

    def test_a_second_daemon_does_not_start_while_one_is_running(
        self, daemon: Daemon
    ) -> None:
        assert serve(0) is False
        assert read_live_daemon_state() == daemon.state

    def test_removes_its_state_file_on_a_clean_stop(self, daemon: Daemon) -> None:
        terminate(daemon.process)
        assert read_live_daemon_state() is None

    def test_a_stopped_daemon_is_replaced_by_a_fresh_one_with_a_new_token(
        self, repo: Repo, start_daemon: Callable[[int], Daemon]
    ) -> None:
        register(repo.project)
        first = start_daemon(0)
        terminate(first.process)
        second = start_daemon(0)
        assert second.state.token != first.state.token

    def test_prunes_a_project_whose_config_is_gone_before_serving(
        self, repo: Repo, make_repo: Callable[[str], Repo], start_daemon: Any
    ) -> None:
        gone = make_repo("gone")
        register(repo.project)
        register(gone.project)
        (gone.project.reportlab / "config.toml").unlink()
        running: Daemon = start_daemon(0)
        assert running.get("/api/health").json()["projects"] == 1


class TestEventStream:
    def test_sends_ready_first_as_text_event_stream(
        self, daemon: Daemon, repo: Repo
    ) -> None:
        with event_stream(daemon, repo.project.id) as stream:
            assert stream.status == 200
            assert "text/event-stream" in stream.content_type
            assert stream.next_event("ready") == {}

    def test_refuses_an_unauthenticated_stream(
        self, daemon: Daemon, repo: Repo
    ) -> None:
        response = httpx.get(f"{daemon.url}/api/p/{repo.project.id}/stream")
        assert response.status_code == 401

    def test_a_stream_of_an_unknown_project_is_404(self, daemon: Daemon) -> None:
        assert daemon.get("/api/p/nope/stream").status_code == 404

    def test_delivers_a_marks_event_when_the_human_marks_a_report(
        self, daemon: Daemon, repo: Repo
    ) -> None:
        repo.write_report("auth", "# Auth\n")
        with event_stream(daemon, repo.project.id) as stream:
            stream.next_event("ready")
            response = httpx.put(
                f"{daemon.url}/api/p/{repo.project.id}/marks",
                params={"path": "auth"},
                headers=daemon.auth,
                json={"read": "2026-09-30T15:00:00Z"},
            )
            assert response.status_code == 200
            assert stream.next_event("marks") == {
                "type": "marks",
                "project": repo.project.id,
                "path": "auth",
            }

    def test_closes_the_loop_a_written_file_reaches_the_browser(
        self, daemon: Daemon, repo: Repo
    ) -> None:
        with event_stream(daemon, repo.project.id) as stream:
            stream.next_event("ready")
            # The daemon's watcher has no ready signal: rewrite until it hears.
            deadline = time.monotonic() + 10
            event: dict[str, Any] | None = None
            version = 0
            while event is None and time.monotonic() < deadline:
                version += 1
                repo.write_report(
                    "auth", f"# Auth flow\n\nsomething happened {version}\n"
                )
                try:
                    event = stream.next_event("report", timeout=0.5)
                except TimeoutError:
                    continue
            assert event == {
                "type": "report",
                "project": repo.project.id,
                "path": "auth",
            }

        document = daemon.get(f"/api/p/{repo.project.id}/report?path=auth").json()
        assert document["title"] == "Auth flow"

    def test_announces_a_deleted_report(self, daemon: Daemon, repo: Repo) -> None:
        file = repo.write_report("auth", "# Auth\n")
        with event_stream(daemon, repo.project.id) as stream:
            stream.next_event("ready")
            deadline = time.monotonic() + 10
            removed: dict[str, Any] | None = None
            while removed is None and time.monotonic() < deadline:
                file.unlink(missing_ok=True)
                try:
                    removed = stream.next_event("report-removed", timeout=0.5)
                except TimeoutError:
                    file.write_text("# Auth\n")
            assert removed is not None
            assert removed["path"] == "auth"

    def test_a_project_attached_while_running_is_picked_up_on_reload(
        self,
        daemon: Daemon,
        make_repo: Callable[[str], Repo],
    ) -> None:
        other = make_repo("other")
        with event_stream(
            daemon, daemon.get("/api/projects").json()[0]["id"]
        ) as stream:
            stream.next_event("ready")
            register(other.project)
            response = httpx.post(f"{daemon.url}/api/reload", headers=daemon.auth)
            assert response.json() == {"projects": 2}
            assert stream.next_event("projects") == {"type": "projects"}
        ids = [p["id"] for p in daemon.get("/api/projects").json()]
        assert other.project.id in ids


def test_the_runtime_files_never_land_outside_the_isolated_state(
    daemon: Daemon, machine_state: Path
) -> None:
    assert (machine_state / "xdg-state" / "r2" / "web" / "daemon.json").is_file()
