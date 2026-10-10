# Tech stack
- Python >=3.13 (uses PEP 695 generics, `type` aliases). uv for env, build (`uv_build` backend, module-root `.`), and running.
- Deps: typer, rich, pydantic 2, pyyaml. Optional `tui`: textual[syntax], textual-image.
- Dev: pytest, ruff, mypy (strict), pyright (standard), taskipy, doc-zero (docs).
- Example projects under `tests/examples/roman/` also use cargo/proptest (Rust) and npm/vitest/fast-check/playwright (TS); not part of r2's own toolchain.
