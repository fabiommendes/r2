"""
Tests for r2.core.cli_tool.CliTool, against `sh`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from r2.core.cli_tool import CliTool

sh = CliTool("sh", echo=False)


def test_available() -> None:
    assert sh.available()


def test_unavailable() -> None:
    assert not CliTool("r2-no-such-program").available()


def test_call_returns_exit_code_and_output_without_raising() -> None:
    result = sh.call("-c", "echo out; echo err >&2; exit 3")
    assert (result.returncode, result.stdout, result.stderr) == (3, "out\n", "err\n")


def test_call_runs_in_path(tmp_path: Path) -> None:
    assert sh.call("-c", "pwd", _path=tmp_path).stdout.strip() == str(tmp_path)


def test_call_merges_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_KEPT", "kept")
    out = sh.call("-c", 'echo "$R2_KEPT $R2_ADDED"', _env={"R2_ADDED": "added"})
    assert out.stdout == "kept added\n"


def test_run_merges_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_KEPT", "kept")
    out = sh.run("-c", 'echo "$R2_KEPT $R2_ADDED"', _env={"R2_ADDED": "added"})
    assert out == "kept added\n"
