# r2 core map

r2 (PyPI `r2-assistant`, formerly "robin"): personal assistant with a Textual TUI that follows Claude Code sessions inside herdr, plus a CLI for humans and coding agents.

## Source map
- `r2/cli/`: Typer app. `app.py` root + project commands (`test`, `build`, `docs`, `init`) and global-flag hoisting; `registry.py` merges builtin/plugin/project commands; `glossary.py`, `threads.py` (issues/ADRs).
- `r2/core/`: domain logic, no UI.
  - `project/`: project tooling (`base.Project` protocol, `py.UvProject`, `get_project`). One submodule per ecosystem.
  - `coverage/`: per-test coverage (`dev/spec/coverage.md`). `base.py` maps/spans/runner ABC, `analysis.py` pure analyses, `py.py` pytest runner, `workspace.py` glue for `r2/cli/coverage.py`. Scratch files under `<project>/.r2/coverage/`.
  - `r2_context.py`: TUI per-project state (`ProjectContext`, `Projects`, `find_root`). Unrelated to `project/`.
  - `cli_tool.py`: `CliTool` wrapper for external programs (run/exec, echo, error policy).
  - `mode.py`: global human/agent mode and verbosity. `console.py`: stdout/stderr consoles.
  - `glossary.py`, `issues.py`, `adrs.py`, `threads.py`: Markdown-backed docs; `files.py`: atomic writes + folder flock.
  - `plugins/`: plugin discovery/loading/manifest.
- `r2/plugin.py`: public plugin API. `r2/builtins/sys/`: builtin plugin.
- `r2/tui/`: Textual app, `views/`, `widgets/`. Optional dependency (`tui` extra).
- `r2/integrations/claude/`: `r2-notify` hook, event and transcript parsing. `integrations/herdr.py`.
- `dev/spec/*.md`: numbered-requirement specs (source of truth for behavior). `dev/issues/`, `dev/adr/`: managed by `r2 issue`/`r2 adr`.
- `tests/examples/`: checked-in fixture projects, excluded from pytest/ruff/pyright. Grouped by feature then language (`tasks/uv/`, `roman/{python,rust,ts}`).

## Invariants
- Agent mode (`--agent` / `R2_AGENT`) never prompts and prints plain text; see `dev/spec/cli.md`.
- Project tasks dispatch via `os.execvpe`, so tests exercise them out of process (`tests/support.run_r2`).

More: stack in `mem:tech_stack`; commands in `mem:suggested_commands`; style rules in `mem:conventions`; pre-commit checks in `mem:task_completion`.
