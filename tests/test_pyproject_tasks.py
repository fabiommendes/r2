"""
Integration tests for r2's PyProject task commands: `r2 test`, `r2 build`,
and `r2 docs`.

Each test copies a hardcoded project from tests/examples/pyproject/ into a
fresh temporary directory (see the `example_project` fixture in
conftest.py), then drives the real `r2` executable against that copy as a
subprocess and checks what it actually did on disk.

The example projects define their tasks the same way a real project would,
under `[tool.taskipy.tasks]` in pyproject.toml, but instead of depending on
the real `taskipy` package they ship a tiny local `taskrunner.py` that reads
that same table and runs the matching command. That keeps the suite
hermetic: no network access and no third-party downloads are needed to
exercise r2 itself, and it still runs through r2's real code path
(`PyProject._try_tasks` -> `uv run task <name>`) exactly as `taskipy` would.
"""

from __future__ import annotations

from r2.testing import ExampleProjectFactory, run_r2


def test_basic_project(example_project: ExampleProjectFactory) -> None:
    project = example_project("basic")
    assert run_r2("test", cwd=project).returncode == 0
    assert run_r2("build", cwd=project).returncode == 0
    assert run_r2("docs", cwd=project).returncode == 0


def test_full_project(example_project: ExampleProjectFactory) -> None:
    project = example_project("full")

    # Tests
    result = run_r2("test", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "TEST_RAN.txt").exists()

    # Build
    result = run_r2("build", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "BUILD_RAN.txt").exists()

    # Docs
    result = run_r2("docs", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "DOCS_RAN.txt").exists()


def test_path_option_targets_the_given_project(
    example_project: ExampleProjectFactory, tmp_path
) -> None:
    """
    `r2 docs --path <dir>` has to run the task inside <dir>, not in whatever
    directory r2 itself happened to be invoked from.
    """
    project = example_project("full")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    result = run_r2("docs", "--path", str(project), cwd=elsewhere)
    assert result.returncode == 0, result.stderr
    assert (project / "DOCS_RAN.txt").exists()
    assert not (elsewhere / "DOCS_RAN.txt").exists()


def test_missing_tasks_are_reported_without_crashing(
    example_project: ExampleProjectFactory,
) -> None:
    project = example_project("no_tasks")
    expectations = {
        "test": ("TEST_RAN.txt", "Could not find the test runner"),
        "docs": ("DOCS_RAN.txt", "Could not build the project documentation"),
    }
    for command, (marker, message) in expectations.items():
        result = run_r2(command, cwd=project)
        assert not (project / marker).exists()
        assert message in result.stderr


def test_build_does_not_run_when_only_a_test_task_exists(
    example_project: ExampleProjectFactory,
) -> None:
    """
    Regression test for a copy-paste bug: `build()` used to look up the
    "test"/"tests" tasks instead of "build"/"builds", so a project with only
    a test task made `r2 build` silently report success without building
    anything.
    """
    project = example_project("test_only")

    result = run_r2("test", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "TEST_RAN.txt").exists()

    result = run_r2("build", cwd=project)
    assert result.returncode == 0


def test_plural_and_synonym_task_names_are_recognized(
    example_project: ExampleProjectFactory,
) -> None:
    project = example_project("plural_tasks")

    result = run_r2("test", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "TEST_RAN.txt").exists()

    result = run_r2("build", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "BUILD_RAN.txt").exists()

    result = run_r2("docs", cwd=project)
    assert result.returncode == 0, result.stderr
    assert (project / "DOCS_RAN.txt").exists()


def test_directory_without_pyproject_toml_is_rejected(
    example_project: ExampleProjectFactory,
) -> None:
    project = example_project("not_a_project")
    result = run_r2("test", cwd=project)
    assert result.returncode != 0
    assert "Could not determine the project type" in result.stderr
