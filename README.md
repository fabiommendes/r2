# r2

[![CI](https://github.com/fabiommendes/r2/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fabiommendes/r2/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/r2-assistant.svg)](https://pypi.org/project/r2-assistant/)

R2 is a personal computer assistant with two faces:

- a **TUI**, a sidekick for Claude Code. Run `r2` with no arguments in a
  terminal split next to [herdr](https://herdr.dev);
- a **command line** for humans and coding agents: `r2 glossary`, the project
  commands `r2 test`, `r2 build` and `r2 docs`, and whatever plugins add. An
  agent mode keeps the output short and refuses destructive commands without
  an explicit go-ahead.

I assume this project is not useful for anyone else but me, but feel free to
fork it if you want to use it as inspiration. The command line assumes some
things about my setup:

- I use Nix Packages on Debian Trixie.
- I use Chezmoi to manage my dotfiles.
- I use GNOME as my main desktop environment.
- I use UV to manage Python and all Python apps (including this) in my system.
- It sometimes assumes some specific applications are installed.

## Installation

```bash
uv tool install "r2-assistant[tui]"
```

The `tui` extra pulls in Textual. Without it you get the command line and the
hook only, and `r2` with no arguments tells you to install the extra. You can
also skip the install and create an alias in your shell configuration:

```sh
alias r2="uvx --from 'r2-assistant[tui]' r2"
```

This installs two commands: `r2`, and `r2-notify`, the Claude Code hook that
feeds the TUI.

R2 used to be called robin. `robin-notify` still works as an alias of
`r2-notify`, so existing hook settings keep working, but point them to
`r2-notify` when you can. The first run of the TUI copies
`~/.config/robin/config.json` to `~/.local/state/r2/tui.json` if there is no
r2 state yet. `ROBIN_EDITOR` and `ROBIN_IDE` are now `R2_EDITOR` and `R2_IDE`.

## Commands

`r2` with no arguments opens the TUI. With arguments, it runs one of these
commands.

**`r2 help`**

List every available command as plain text, one per line, with tags such as
`[project]`, `[global]`, `[destructive]` for commands that come from plugins.
`--all` includes hidden commands. `r2 --help` is the usual Typer help.

**`r2 glossary sort|add|remove`**

Manage a `GLOSSARY.md` file (or the one given with `--file`): a title, an
introduction, a `---` line, and one `## Term` section per definition.
`add "name: definition"` adds a term and `remove NAME` drops one. Both sort
the terms alphabetically, as does `sort`.

**`r2 test`, `r2 build`, `r2 docs`**

Run the default test, build or documentation task of the project in the
current directory (or the one given with `--path`). For a `pyproject.toml`
project, r2 runs the matching [taskipy](https://github.com/taskipy/taskipy)
task through `uv run task`, and falls back to `pytest`, `uv build` or
`doc-zero build` when the task does not exist.

## Agent mode

`r2 --agent <command>` (or `R2_AGENT=1` in the environment) turns on the
conventions meant for coding agents, for every command:

- No interactive prompts. A command that would ask a question exits with an
  error that says how to pass the answer inline.
- Subprocesses run with stdin closed, unless a project command is marked
  `interactive`.
- Output of project commands is reduced to a summary: one `ok: <name>` line
  on success; exit code plus the last 30 lines of output on failure.
  `r2 --agent --full <command>` disables the reduction.
- Commands marked `destructive` refuse to run without `r2 --yes`.

## Plugins

There are two tiers. Builtin commands always win a name collision, then
project commands, then global plugin commands. `r2 plugins list` shows what
was found and what was shadowed; `r2 plugins doctor` imports every global
plugin and checks it against its manifest.

### Project commands

Put an `r2.toml` at the project root (or a `[tool.r2]` table in
`pyproject.toml`; `r2.toml` wins when both exist). It is found walking up
from the current directory.

```toml
[commands.db-reset]
run = "uv run python scripts/db.py reset"   # a shell command, run from the project root
help = "Drop and recreate the dev database."
destructive = true      # needs `r2 --yes` in agent mode
args = "passthrough"    # or "none"; extra arguments are appended to `run`
cwd = "."               # relative to the project root
env = { APP_ENV = "dev" }
timeout = 300           # seconds; exit code 124 on expiry
interactive = false     # true keeps stdin open
output = "summary"      # or "passthrough": never reduced, even in agent mode

[config.sys]            # overrides a global plugin's settings for this project
hd = "~/hd2"
```

Project commands are plain shell commands, so they run in the project's own
environment, not in r2's. Nothing Python is imported from the project.

### Global plugins

A global plugin is a folder under `$R2_CONFIG_DIR/plugins/` (default
`~/.config/r2/plugins/`) with a manifest and a Python package:

```
~/.config/r2/plugins/sys/
├── plugin.toml
└── __init__.py
```

```toml
# plugin.toml
[plugin]
name = "sys"
help = "Machine-specific helpers."

[commands.hd]
help = "Move a path to the hard drive and leave a symlink in its place."
destructive = true
hidden = true           # left out of `r2 help` (see `r2 help --all`)
```

```python
# __init__.py
from pathlib import Path
from pydantic import BaseModel
from r2.plugin import Plugin


class SysConfig(BaseModel):
    hd: Path = Path("~/hd")


plugin = Plugin("sys", config=SysConfig)


@plugin.command()
def hd(path: Path) -> None:
    """Move PATH to the hard drive."""
    target = plugin.settings.hd.expanduser()
    ...
```

Command functions are ordinary Typer commands. Only `plugin.toml` is read at
startup; the package is imported when one of its commands runs, so a broken
plugin costs nothing until used and `r2 plugins doctor` finds it.

Settings come from `[plugins.<name>]` in `$R2_CONFIG_DIR/config.toml`, with
`[config.<name>]` from the project manifest layered on top, validated by the
plugin's pydantic model.

### TUI panes

A global plugin can also add tabs to the TUI, after r2's own views. It
declares them in `plugin.toml` and registers a `r2.tui.PluginPane` subclass
for each one:

```toml
[panes.aliases]
title = "Aliases"       # tab label; defaults to the pane name
```

```python
from textual.widgets import DataTable
from r2.tui import PaneCommand, PluginPane


@plugin.pane()  # name from the class: AliasesPane -> "aliases"
class AliasesPane(PluginPane):
    GLOBAL_COMMANDS = [PaneCommand("reload", "Reload aliases", key="ctrl+r")]
    LOCAL_COMMANDS = [PaneCommand("add", "Add alias", key="a")]

    def compose(self):
        yield DataTable()

    def action_reload(self) -> None: ...
    def action_add(self) -> None: ...
```

A pane is a regular Textual widget with three extra contracts:

- **Commands.** `GLOBAL_COMMANDS` are bound on the whole app and run on
  their pane even when another tab is active (call `self.activate()` to
  bring it forward). `LOCAL_COMMANDS` are bound only while focus is inside
  the pane. Both appear in the command palette; local ones only while their
  pane is active. A global key that r2 or another plugin already uses is
  skipped and reported as a notification; the palette entry stays.
- **Navigation.** `←` / `→` move to the neighbor tab when
  `should_leave(direction)` returns true; otherwise the key reaches the
  focused widget. The default knows `Input`, `TextArea` and `DataTable`
  (leave only when the cursor is at the edge) and keeps the key for any
  other widget that binds it. `alt+←` / `alt+→` always move.
- **Entering.** `enter(direction)` runs when the tab becomes active and
  focuses the pane or its first focusable widget by default. Override
  `current_link()` to make `e` and `o` work on the pane, and `reload()` for
  `F5`.

### Builtin plugins

Some plugins ship with r2. `[r2] builtins` in `~/.config/r2/config.toml`
picks which ones load, and in which order their tabs appear:

```toml
[r2]
builtins = ["sys"]
```

`r2 plugins list` shows the builtins that are off. A plugin in
`~/.config/r2/plugins/` with the name of a builtin replaces it.

- **`sys`** holds the commands tied to my machine: `r2 hd PATH` moves a path
  to a hard drive mounted under `$HOME` and leaves a symlink; `r2 alias` adds
  entries to `~/.bash_aliases`, with shortcuts for `uvx` (`--py`) and `npx`
  (`--js`) wrappers, and lists them with `--list` or `--sections`. Off by
  default. Its settings:

  ```toml
  [plugins.sys]
  hd = "~/hd"
  aliases = "~/.bash_aliases"
  ```

## The TUI

The TUI follows Claude Code sessions. Run it in a terminal split next to
[herdr](https://herdr.dev): it follows the herdr pane in focus and shows what
the Claude session in that pane is doing, including the files it reads and the
`path/to/file.py:20-56` references it mentions in its answers.

### Setup

Register the hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Read|Edit|Write", "hooks": [{"type": "command", "command": "r2-notify"}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "command": "r2-notify"}]}
    ]
  }
}
```

Then split your terminal, run `herdr` on one side and `r2` on the other.

The hook appends each event to `$XDG_STATE_HOME/r2/events.jsonl`
(`~/.local/state/r2/events.jsonl` by default), so r2 picks up what
happened even if it was not running at the time. Without herdr, r2 shows
the project of the directory it was started in.

### Views

R2 has four tabs. Each one has a drawer on the left and content on the
right. Drag the bar between them to resize the drawer.

1. **Live**: the files Claude read and the references it wrote in its last
   answers, newest first, with a preview of the selected one.
2. **Project**: the project tree, without the files git ignores, and a
   preview of the selected file. Markdown files are rendered, as in Docs.
3. **Docs**: the Markdown files in `dev/docs`, `dev/spec` and `docs`. The
   frontmatter shows in a bar above the document instead of in the text.
4. **Issues**: the issues in `dev/issues`, grouped by status. The groups of
   closed issues start folded. `/` filters the issues: each word must start a
   word of the title, file name or metadata, and `key:value` looks in one key
   only, as in `tag:ui` or `kind:defect`. Comments show as a thread of collapsible cards. Press `n` to fill
   in a form with the metadata of a new issue; r2 writes the file and opens
   it in the editor. The format is described in `dev/spec/issues.md`.

When a reference has a line range, the preview shows an excerpt around it.
Press `f` to switch between the excerpt and the whole file. Images are shown
inline when the terminal supports it.

The top bar shows the project, its git branch, and whether the worktree is
clean, has staged changes or has unstaged changes. Click the `⭘` icon on its
left to open the command palette, where you can also change the theme.

### Keys

| Key | Action |
| --- | --- |
| `1` to `4` | Switch to a view |
| `←` `→` | Move between drawer and content, then to the previous or next view |
| `f` | Toggle excerpt and whole file |
| `e` | Edit the current file in the terminal editor |
| `o` | Open the current file in its default application |
| `i` | Open the project in the GUI editor |
| `t` | Open a shell in the project root |
| `p` | Pin the current project instead of following herdr focus |
| `n` | Create an issue (Issues view) |
| `c` | Comment on the issue on display (Issues view) |
| `s` | Change the status of the issue on display (Issues view) |
| `/` | Filter the issues (Issues view) |
| `F5` | Read the file on display and the git status again |
| `q` | Quit |

In the trees, `→` expands a node (in the Project tree, it opens a file) and `←`
folds an open node or goes up to its parent before leaving the tree.

### Configuration

R2 picks the programs it launches from the environment:

- `e` runs `$R2_EDITOR`, `$EDITOR` or `$VISUAL`, falling back to `micro`.
  It passes `+LINE` to jump to the reference.
- `i` runs `$R2_IDE` or `$VISUAL`, falling back to `code`.
- `t` runs `$SHELL`.

R2 saves the theme and the width of each drawer in
`$XDG_STATE_HOME/r2/tui.json` (`~/.local/state/r2/tui.json` by default).
It is state, not configuration, so you should not need to edit it; the
first run copies an older `~/.config/r2/config.json` there:

```json
{
  "drawer_widths": {"live": 30, "project": 40, "docs": 30, "issues": 30},
  "theme": "nord"
}
```

A missing or broken file falls back to the defaults.
