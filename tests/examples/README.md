# Example projects

Checked-in projects that r2's test suite runs commands against. pytest does
not collect anything here (`norecursedirs` in `pyproject.toml`), and ruff and
pyright skip this tree.

- `tasks/uv/`: uv projects with different task setups, for the project task
  commands (`r2.core.project`). Tests copy them to a temp dir through the
  `example_project` fixture in `tests/conftest.py`.
- `roman/`: the same small library in Python, Rust and TypeScript, with a
  known catalog of tests. It is the baseline for the test analysis commands
  (per-test coverage, redundancy, mutation testing). See `roman/README.md`.
- `stories/codehood/`: a slice of the codehood user stories (the admin role)
  and its playwright story tests, copied as is. It is the acceptance fixture
  of `r2 story`; the tests copy it to a temp dir before writing.

Group new examples by the feature they exercise first, and by language or
tool second.
