# Conventions
- Lint: must pass ruff, mypy strict and pyright. Suppress per tool only (`# pyright: ignore[rule]`, `# type: ignore[code]`), never bare `# type: ignore`.
- Frozen dataclasses for value objects; `object.__setattr__` in `__post_init__` when deriving fields.
- `match` + `assert_never` for exhaustive Literal handling.
- Docstrings: triple quotes on their own lines, short imperative/descriptive text. Low comment density.
- One submodule per ecosystem/language inside a domain package (`project/py.py`; planned `coverage/{py,rs,ts}.py`), with an abstract base in `base.py`.
- Specs in `dev/spec/` use frontmatter (`type: spec`, `status`), numbered requirements, tables; implementation follows them.
- Commit after each feature cycle; message ends with Co-Authored-By trailer.
- Prose (docs, specs, commits) avoids em-dashes and buzzwords.
