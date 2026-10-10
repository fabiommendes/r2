# Commands
- `uv run task test` (pytest, ~1 min; spawns `uv run r2` subprocesses).
- `uv run task lint`: ruff check + ruff format --check + `mypy r2` + `pyright r2 tests`.
- `uv run task format`: ruff format + ruff check --fix.
- `uv run task docs`: doc-zero build (regenerates `docs/conf.py`).
- `uv run r2 ...`: run this checkout's CLI.
- Shell is fish; a PreToolUse hook rewrites git/grep/ls/find to `rtk` (filtered output, truncates long grep). `rtk proxy <cmd>` for raw output.
- Inside `tests/examples/roman/python`, `VIRTUAL_ENV` from r2's venv triggers a harmless uv warning.
