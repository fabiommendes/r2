"""
Shared fixtures for r2's integration tests.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from r2.core.conf import Config
from r2.core.plugins import loader
from tests.support import EXAMPLES_ROOT, ROMAN_ROOT, ExampleProjectFactory


@pytest.fixture(scope="session", autouse=True)
def _require_uv() -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH; r2 needs it to run tests")


@pytest.fixture
def example_project() -> Iterator[ExampleProjectFactory]:
    """
    Factory fixture for the hardcoded projects under tests/examples/tasks/uv/.

    Call it with an example's directory name to get a copy in a fresh
    temporary directory:

        def test_something(example_project):
            project_dir = example_project("full")
            ...

    Every copy this factory hands out is removed at teardown, pass or fail,
    so tests never leave anything behind and never mutate the checked-in
    fixtures under tests/examples/tasks/uv/.
    """
    made: list[Path] = []

    def _make(name: str) -> Path:
        source = EXAMPLES_ROOT / name
        if not source.is_dir():
            raise FileNotFoundError(f"No example project named {name!r} at {source}")

        # We clean any eventual .venv folder leftover
        if (source / ".venv").exists():
            shutil.rmtree(source / ".venv", ignore_errors=True)

        temp_dir = Path(tempfile.mkdtemp(prefix=f"r2-test-{name}-"))
        made.append(temp_dir)

        target = temp_dir / name
        shutil.copytree(source, target)
        return target

    yield _make

    for temp_dir in made:
        shutil.rmtree(temp_dir, ignore_errors=True)


ROMAN_IGNORE = shutil.ignore_patterns(
    ".venv",
    "node_modules",
    "target",
    ".r2",
    ".hypothesis",
    ".coverage*",
    "__pycache__",
    "test-results",
    "playwright-report",
)


@pytest.fixture
def roman_project(tmp_path_factory: pytest.TempPathFactory) -> ExampleProjectFactory:
    """
    Factory fixture for tests/examples/roman/<language>: a copy without
    build artifacts in a fresh temporary directory.
    """

    def _make(language: str) -> Path:
        source = ROMAN_ROOT / language
        if not source.is_dir():
            raise FileNotFoundError(f"No roman example for {language!r} at {source}")
        target = tmp_path_factory.mktemp(f"roman-{language}") / language
        shutil.copytree(source, target, ignore=ROMAN_IGNORE)
        return target

    return _make


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run r2 against a private config dir, state dir and herdr socket."""
    config = tmp_path / "config"
    (config / "plugins").mkdir(parents=True)
    (config / "config.toml").write_text("")
    monkeypatch.setenv("R2_CONFIG_DIR", str(config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    monkeypatch.setenv("HERDR_SOCKET_PATH", str(tmp_path / "no-herdr.sock"))
    monkeypatch.delenv("R2_AGENT", raising=False)
    monkeypatch.chdir(tmp_path)
    Config.reset()
    loader.reset()
    return config
