"""
Tests for the plugin system: discovery of global plugins and project
manifests, lazy loading, name precedence, agent-mode conventions, and the
`r2 plugins` commands.

Every test gets a private config dir (via R2_CONFIG_DIR) and a private
project dir, and drives the root app in-process with Typer's CliRunner.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import build_app
from r2.core.conf import Config
from r2.core.plugins import loader

runner = CliRunner()

PLUGIN_TOML = """
[plugin]
name = "{name}"
help = "Test plugin."

{commands}
"""

PLUGIN_INIT = """
from r2.plugin import Plugin
from pydantic import BaseModel

class Settings(BaseModel):
    greeting: str = "hi"

plugin = Plugin("{name}", config=Settings)

@plugin.command()
def greet(who: str = "world") -> None:
    print(f"{{plugin.settings.greeting}} {{who}}")
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Isolated config dir + project dir. Returns the project dir.
    """
    config = tmp_path / "config"
    (config / "plugins").mkdir(parents=True)
    (config / "config.toml").write_text("")
    monkeypatch.setenv("R2_CONFIG_DIR", str(config))
    monkeypatch.delenv("R2_AGENT", raising=False)
    Config.reset()
    loader.reset()

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    return project


def plugins_dir() -> Path:
    return Path(os.environ["R2_CONFIG_DIR"]) / "plugins"


def write_plugin(name: str, commands: str, init: str | None = None) -> Path:
    root = plugins_dir() / name
    root.mkdir()
    (root / "plugin.toml").write_text(
        PLUGIN_TOML.format(name=name, commands=textwrap.dedent(commands))
    )
    (root / "__init__.py").write_text(
        textwrap.dedent(init if init is not None else PLUGIN_INIT.format(name=name))
    )
    return root


def write_manifest(project: Path, body: str, pyproject: bool = False) -> None:
    body = textwrap.dedent(body)
    if pyproject:
        (project / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0"\n\n'
            + body.replace("[commands.", "[tool.r2.commands.")
        )
    else:
        (project / "r2.toml").write_text(body)


def run(*args: str):
    return runner.invoke(build_app(), list(args))


#
# Global plugins
#
def test_global_plugin_command_runs(env: Path) -> None:
    write_plugin("hello", '[commands.greet]\nhelp = "Greet."')
    result = run("greet", "--who", "bob")
    assert result.exit_code == 0, result.output
    assert "hi bob" in result.output


def test_plugin_is_not_imported_until_its_command_runs(env: Path) -> None:
    write_plugin("broken", '[commands.greet]\nhelp = "Greet."', init="def (:")

    result = run("help")
    assert result.exit_code == 0, result.output
    assert "r2 greet" in result.output

    result = run("greet")
    assert result.exit_code == 1
    assert "failed to import" in result.output
    assert "SyntaxError" in result.output


def test_bad_manifest_is_reported_and_skipped(env: Path) -> None:
    write_plugin("bad", "[commands.greet]\nbogus = true")
    write_plugin("good", '[commands.greet]\nhelp = "Greet."')

    result = run("plugins", "list")
    assert result.exit_code == 0, result.output
    assert "problem" in result.output and "bogus" in result.output
    assert "global   good" in result.output

    result = run("plugins", "doctor")
    assert result.exit_code == 1


def test_doctor_catches_declared_but_undefined_command(env: Path) -> None:
    write_plugin("hello", '[commands.greet]\n[commands.wave]\nhelp = "Wave."')
    result = run("plugins", "doctor")
    assert result.exit_code == 1
    assert "'wave'" in result.output


def test_plugin_settings_merge_global_and_project(env: Path) -> None:
    write_plugin("hello", "[commands.greet]")
    (Path(os.environ["R2_CONFIG_DIR"]) / "config.toml").write_text(
        '[plugins.hello]\ngreeting = "hello"\n'
    )
    Config.reset()
    assert "hello world" in run("greet").output

    write_manifest(env, '[config.hello]\ngreeting = "yo"\n')
    assert "yo world" in run("greet").output


#
# Project manifests
#
def test_project_command_runs_with_passthrough_args(env: Path) -> None:
    write_manifest(env, '[commands.say]\nrun = "echo"\nhelp = "Echo."')
    result = run("--agent", "say", "a b", "c")
    # In agent mode output is summarized: one line on success.
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "ok: say"


def test_project_command_from_pyproject_tool_table(env: Path) -> None:
    write_manifest(env, '[commands.say]\nrun = "echo"\n', pyproject=True)
    result = run("plugins", "list")
    assert "pyproject.toml" in result.output and "say" in result.output


def test_r2_toml_wins_over_pyproject(env: Path) -> None:
    write_manifest(env, '[commands.one]\nrun = "echo"\n', pyproject=True)
    write_manifest(env, '[commands.two]\nrun = "echo"\n')
    result = run("plugins", "list")
    assert "r2.toml" in result.output and "two" in result.output
    assert "one" not in result.output


def test_manifest_is_found_from_a_subdirectory(env: Path) -> None:
    write_manifest(env, '[commands.say]\nrun = "echo"\n')
    sub = env / "a" / "b"
    sub.mkdir(parents=True)
    os.chdir(sub)
    assert "say" in run("plugins", "list").output


def test_failed_project_command_reports_exit_code_and_tail(env: Path) -> None:
    write_manifest(env, '[commands.boom]\nrun = "echo out; echo err >&2; exit 3"\n')
    result = run("--agent", "boom")
    assert result.exit_code == 3
    assert "failed: boom (exit 3)" in result.output
    assert "out" in result.output and "err" in result.output


def test_args_none_rejects_extra_arguments(env: Path) -> None:
    write_manifest(env, '[commands.say]\nrun = "echo"\nargs = "none"\n')
    result = run("say", "x")
    assert result.exit_code == 2
    assert "takes no arguments" in result.output


def test_project_command_runs_in_declared_cwd_and_env(env: Path) -> None:
    (env / "sub").mkdir()
    write_manifest(
        env,
        '[commands.where]\nrun = "basename $PWD; echo $R2_TEST_VAR"\n'
        'cwd = "sub"\nenv = { R2_TEST_VAR = "set" }\n',
    )
    # Not in agent mode the output is not captured, so summarize via --agent --full
    # would also passthrough; use summary mode on failure to read output instead.
    write_manifest(
        env,
        '[commands.where]\nrun = "basename $PWD; echo $R2_TEST_VAR; exit 1"\n'
        'cwd = "sub"\nenv = { R2_TEST_VAR = "set" }\n',
    )
    result = run("--agent", "where")
    assert "sub" in result.output and "set" in result.output


def test_timeout(env: Path) -> None:
    write_manifest(env, '[commands.slow]\nrun = "sleep 5"\ntimeout = 0.2\n')
    result = run("slow")
    assert result.exit_code == 124
    assert "timed out" in result.output


#
# Precedence
#
def test_project_command_shadows_global_command(env: Path) -> None:
    write_plugin("hello", "[commands.greet]")
    write_manifest(env, '[commands.greet]\nrun = "echo from-project"\n')
    result = run("--agent", "greet")
    assert result.output.strip() == "ok: greet"
    assert (
        "shadowed global command 'greet' (taken by project command)"
        in run("plugins", "list").output
    )


def test_builtin_command_cannot_be_shadowed(env: Path) -> None:
    write_manifest(env, '[commands.help]\nrun = "echo nope"\n')
    result = run("help")
    assert result.exit_code == 0
    assert "r2 glossary" in result.output
    assert "taken by builtin command" in run("plugins", "list").output


#
# Agent conventions
#
def test_destructive_command_needs_yes_in_agent_mode(env: Path) -> None:
    write_manifest(env, '[commands.rm]\nrun = "echo gone"\ndestructive = true\n')

    assert run("rm").exit_code == 0

    result = run("--agent", "rm")
    assert result.exit_code == 2
    assert "destructive" in result.output

    assert run("--agent", "--yes", "rm").exit_code == 0


def test_agent_mode_from_environment(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_manifest(env, '[commands.rm]\nrun = "echo gone"\ndestructive = true\n')
    monkeypatch.setenv("R2_AGENT", "1")
    assert run("rm").exit_code == 2


def test_help_lists_tags_and_hides_hidden_commands(env: Path) -> None:
    write_plugin(
        "hello", '[commands.greet]\nhelp = "Greet."\nhidden = true\ndestructive = true'
    )
    write_manifest(env, '[commands.say]\nrun = "echo"\nhelp = "Say."\n')

    out = run("help").output
    assert "r2 say" in out and "[project] Say." in out
    assert "greet" not in out

    out = run("help", "--all").output
    assert "[global] [destructive] [hidden] Greet." in out
