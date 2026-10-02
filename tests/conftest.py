"""
Shared fixtures for r2's integration tests.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.support import EXAMPLES_ROOT, ExampleProjectFactory


@pytest.fixture(scope="session", autouse=True)
def _require_uv() -> None:
    if shutil.which("uv") is None:
        pytest.skip("uv is not on PATH; r2 needs it to run tests")


@pytest.fixture
def example_project() -> Iterator[ExampleProjectFactory]:
    """
    Factory fixture for the hardcoded projects under tests/examples/pyproject/.

    Call it with an example's directory name to get a copy in a fresh
    temporary directory:

        def test_something(example_project):
            project_dir = example_project("full")
            ...

    Every copy this factory hands out is removed at teardown, pass or fail,
    so tests never leave anything behind and never mutate the checked-in
    fixtures under tests/examples/pyproject/.
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
