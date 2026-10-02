"""Import guards: the CLI and the hook must stay light.

Each module is imported in a fresh interpreter, since sys.modules in the test
process already holds everything the other tests imported.
"""

import json
import subprocess
import sys

import pytest

TUI_MODULES = {"textual", "textual_image"}
HEAVY_MODULES = TUI_MODULES | {"yaml", "typer", "pydantic", "rich", "click"}


def imported(module: str) -> set[str]:
    """Return the top-level packages loaded by importing module."""
    code = (
        "import json, sys\n"
        f"import {module}\n"
        "print(json.dumps(sorted({name.split('.')[0] for name in sys.modules})))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return set(json.loads(result.stdout))


def test_cli_does_not_import_the_tui() -> None:
    assert not imported("r2.cli") & TUI_MODULES


def test_cli_commands_do_not_import_the_tui() -> None:
    assert not imported("r2.cli.app") & TUI_MODULES


def test_notify_hook_imports_only_the_stdlib() -> None:
    assert not imported("r2.integrations.claude.notify") & HEAVY_MODULES


@pytest.mark.parametrize("module", ["r2", "r2.core.config", "r2.core.links"])
def test_core_does_not_import_the_tui(module: str) -> None:
    assert not imported(module) & TUI_MODULES
