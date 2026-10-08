"""
Tests for the global options of the root `r2` command (dev/spec/cli.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from r2.cli import main
from r2.cli.app import hoist_globals, take_directory
from r2.core.mode import configure


#
# Verbosity
#
@pytest.mark.parametrize(
    ("agent", "verbose", "quiet", "level"),
    [
        (False, 0, 0, 0),
        (True, 0, 0, -1),
        (False, 0, 1, -1),
        (False, 0, 2, -2),
        (True, 1, 0, 0),
        (False, 2, 0, 2),
        (False, 1, 1, 0),
        (True, 1, 1, -1),
    ],
)
def test_verbosity_counts_from_the_mode_default(
    agent: bool, verbose: int, quiet: int, level: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("R2_AGENT", raising=False)
    assert configure(agent=agent, verbose=verbose, quiet=quiet).verbosity == level


def test_agent_environment_variable_lowers_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("R2_AGENT", "1")
    assert configure().verbosity == -1


#
# Hoisting
#
def test_global_flags_after_a_builtin_command_move_to_the_front() -> None:
    args = ["glossary", "list", "--json", "-qv", "--tag", "x"]
    assert hoist_globals(args, passthrough=set()) == [
        "--json",
        "-qv",
        "glossary",
        "list",
        "--tag",
        "x",
    ]


def test_flags_before_the_command_stay_in_place() -> None:
    args = ["--agent", "glossary", "list", "-v"]
    assert hoist_globals(args, passthrough=set()) == [
        "--agent",
        "-v",
        "glossary",
        "list",
    ]


def test_passthrough_commands_keep_their_arguments() -> None:
    args = ["-q", "test", "-v", "--json"]
    assert hoist_globals(args, passthrough={"test"}) == args


def test_nothing_after_double_dash_moves() -> None:
    args = ["glossary", "find", "--", "-v"]
    assert hoist_globals(args, passthrough=set()) == args


def test_other_short_options_do_not_move() -> None:
    args = ["glossary", "list", "-f", "G.md", "-vx"]
    assert hoist_globals(args, passthrough=set()) == args


#
# -C
#
@pytest.mark.parametrize(
    "args",
    [["-C", "sub", "glossary"], ["-Csub", "glossary"], ["-C=sub", "glossary"]],
)
def test_take_directory_removes_the_option(args: list[str]) -> None:
    assert take_directory(args) == (["glossary"], Path("sub"))


def test_take_directory_ignores_options_after_the_command() -> None:
    args = ["make", "-C", "sub"]
    assert take_directory(args) == (args, None)


def test_c_runs_r2_in_the_directory(
    config: Path, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "r2.toml").write_text('[commands.where]\nrun = "pwd"\n')

    with pytest.raises(SystemExit) as exit:
        main(["-C", str(sub), "where"])

    assert exit.value.code == 0
    assert capfd.readouterr().out.strip() == str(sub)
