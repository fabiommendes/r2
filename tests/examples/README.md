# Example projects

Checked-in projects that r2's test suite runs commands against. pytest does
not collect anything here (`norecursedirs` in `pyproject.toml`), and ruff and
pyright skip this tree.

- `tasks/uv/`: uv projects with different task setups, for the project task
  commands (`r2.core.tasks`). Tests copy them to a temp dir through the
  `example_project` fixture in `tests/conftest.py`.
- `roman/`: the same small library in Python, Rust and TypeScript, with a
  known catalog of tests. It is the baseline for the test analysis commands
  (per-test coverage, redundancy, mutation testing). See `roman/README.md`.

Group new examples by the feature they exercise first, and by language or
tool second.
