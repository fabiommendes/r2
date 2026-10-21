from __future__ import annotations

import os
import stat
import subprocess
import sys

import pytest

from r2.web.paths import daemon_file, lock_file, state_dir
from r2.web.state import (
    BIND_ADDRESS,
    DEFAULT_PORT,
    DaemonState,
    alive,
    clear_daemon_state,
    daemon_lock,
    new_token,
    read_daemon_state,
    read_live_daemon_state,
    write_daemon_state,
)


def a_dead_pid() -> int:
    """The pid of a process that has already exited."""
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def state(pid: int, port: int = 7717) -> DaemonState:
    return DaemonState(pid=pid, port=port, token="secret", started="2026-10-20T10:00")


class TestPaths:
    def test_machine_wide_files_live_under_xdg_state_home(
        self, machine_state: object
    ) -> None:
        base = os.environ["XDG_STATE_HOME"]
        assert str(state_dir()) == f"{base}/r2/web"
        assert daemon_file().parent == state_dir()
        assert lock_file().parent == state_dir()

    def test_falls_back_to_the_local_state_directory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_STATE_HOME")
        monkeypatch.setenv("HOME", "/somewhere")
        assert str(state_dir()) == "/somewhere/.local/state/r2/web"


class TestDaemonState:
    def test_the_daemon_listens_on_loopback_only(self) -> None:
        assert BIND_ADDRESS == "127.0.0.1"
        assert DEFAULT_PORT == 7717

    def test_round_trips(self) -> None:
        write_daemon_state(state(os.getpid(), 7800))
        assert read_daemon_state() == state(os.getpid(), 7800)

    def test_the_file_is_private_because_it_holds_the_token(self) -> None:
        write_daemon_state(state(os.getpid()))
        assert stat.S_IMODE(daemon_file().stat().st_mode) == 0o600

    def test_no_file_means_no_state(self) -> None:
        assert read_daemon_state() is None
        assert read_live_daemon_state() is None

    def test_a_corrupt_file_means_no_state(self) -> None:
        daemon_file().parent.mkdir(parents=True)
        daemon_file().write_text("{ not json")
        assert read_daemon_state() is None

    def test_a_state_with_a_live_pid_is_live(self) -> None:
        write_daemon_state(state(os.getpid()))
        assert read_live_daemon_state() == state(os.getpid())

    def test_a_state_with_a_dead_pid_is_the_same_as_no_state(self) -> None:
        write_daemon_state(state(a_dead_pid()))
        assert read_live_daemon_state() is None
        assert read_daemon_state() is not None

    def test_clearing_removes_the_file_and_is_not_an_error_twice(self) -> None:
        write_daemon_state(state(os.getpid()))
        clear_daemon_state()
        clear_daemon_state()
        assert not daemon_file().exists()

    def test_tokens_are_unguessable_and_distinct(self) -> None:
        tokens = {new_token() for _ in range(5)}
        assert len(tokens) == 5
        assert all(len(token) >= 32 for token in tokens)

    def test_alive(self) -> None:
        assert alive(os.getpid())
        assert not alive(a_dead_pid())


class TestDaemonLock:
    def test_the_first_holder_gets_it_and_a_second_does_not(self) -> None:
        with daemon_lock() as first:
            assert first
            with daemon_lock() as second:
                assert not second

    def test_is_free_again_once_released(self) -> None:
        with daemon_lock():
            pass
        with daemon_lock() as again:
            assert again

    def test_is_dropped_when_its_holder_dies(self) -> None:
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys; from r2.web.state import daemon_lock\n"
                "with daemon_lock() as got:\n"
                "    print(int(got), flush=True)\n"
                "    sys.stdin.read()\n",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "1"
        with daemon_lock() as while_held:
            assert not while_held
        holder.kill()
        holder.wait()
        with daemon_lock() as after_death:
            assert after_death
