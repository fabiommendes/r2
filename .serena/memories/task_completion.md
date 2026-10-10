# Done checklist
1. `uv run task lint` clean (ruff, format check, mypy r2, pyright r2 tests).
2. `uv run task test` passes.
3. If a module moved/was added under `r2/`, update `docs/api/*.rst` and `docs/api/_index.rst`.
4. If behavior changed, update the matching `dev/spec/*.md`.
5. Commit only the files of the feature; leave unrelated working-tree changes (e.g. `dev/issues/`, `GLOSSARY.md`) alone.
