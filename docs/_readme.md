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

**`r2 glossary`**

Read and edit the project glossary: `GLOSSARY.md` at the project root, or
the file given with `--file`. The format is in `dev/spec/glossary.md`.

| Command | Does |
| --- | --- |
| `list [--tag T]` | one line per term: `Name: first sentence` |
| `show TERM` | the term's section, as written |
| `find WORDS` | terms matching the words; a word to avoid prints `gadget -> Widget` |
| `check` | duplicate terms, avoided words that are terms, broken `related`; exits 1 on problems |
| `add "Name: definition"` | add a term; human mode prompts for a missing definition |
| `set TERM` | change a term: `--definition`, field options, `--unset KEY` |
| `remove TERM` | remove a term |
| `fmt` | rewrite the file in the strict format, terms sorted |

`add` and `set` take the fields as `--tag`, `--avoid`, `--related` and
`--code` (repeatable or comma separated) and `--field key=value` for any
other, such as a translation (`--field pt=termo`). In `set`, each field
option replaces the whole field. `--json` makes `list`, `show`, `find` and
`check` print JSON.

Reading accepts any Markdown file. Writing refuses a file without
`type: glossary` in its frontmatter, so a wrong `--file` never rewrites a
README; `fmt` converts such a file. Writes are atomic and hold a lock on the
folder, so concurrent `r2` processes never lose each other's changes.

**`r2 issue`, `r2 adr`, `r2 rfc`**

Work on the issues in `dev/issues`, the decision records in `dev/adr` and
the feature designs (RFCs) in `dev/rfc` (formats in `dev/spec/issues.md`,
`dev/spec/adrs.md` and `dev/spec/rfcs.md`).

| Command | Does |
| --- | --- |
| `new TITLE [--body TEXT] [--tag T]` | create one and print its path |
| `r2 issue new ... [--kind K] [--priority P] [--milestone M] [--relatedTo R]` | also set these keys; `--kind` without `--body` starts from the template of the kind |
| `list [--status S] [--tag T] [--all]` | `id  status  title`, open ones by default; issues with a plan end with its progress, `3/7` |
| `show ID` | print the file |
| `comment ID TEXT` | add a comment at the end |
| `status ID STATUS` | move to a status |
| `advance ID` | move to the next status of the workflow (`backlog`, `todo`, `in_progress`, `in_review`, `completed`) |
| `r2 rfc new ... [--relatedTo R]` | also set `relatedTo`; without `--body`, the RFC starts with its sections |
| `r2 adr supersede NEW OLD` | record that NEW replaces OLD |

An id is the file name without `.md`, a unique prefix, or the number of an
ADR. Text arguments read stdin when given `-`, so an agent can pass
Markdown without fighting shell quoting:
`r2 issue comment preview-bug - <<'EOF' ... EOF`. Comments and new threads
are signed with `--by NAME`, else `$R2_AUTHOR`, else the git `user.name`.

**`r2 handoff`**

Work on the handoffs in `dev/handoffs` of the main checkout, even from
another worktree (format in `dev/spec/handoffs.md`). A handoff holds the
state of an interrupted session; the `handoff` skill writes it, outside git.

| Command | Does |
| --- | --- |
| `list [--all]` | `id  status  created  title`, the most recent first; open ones by default |
| `show ID` | print the file |
| `take [ID]` | mark an open handoff as taken and print it; without ID, the latest open one |
| `prune [--days N]` | remove the taken handoffs, those older than N days (default 7) and those of closed issues |

**`r2 story`**

Work on the user stories in `docs/user-stories/<role>.md` and check that
they and the e2e tests cite each other (format in `dev/spec/stories.md`). A
story is identified by `role: slug of the title`, such as `student: log-in`;
commands also accept the title, `student: Log in`.

| Command | Does |
| --- | --- |
| `list [--role R] [--status S]` | `id  status  title` |
| `show ID` | print the story |
| `new "ROLE: Title" [--section S] [--status S] [--url U] [--relatedTo R] [--body TEXT]` | add a story to the file of its role |
| `set ID [--title T] [--section S] [--status S] [--url U] [--relatedTo R] [--body TEXT] [--unset KEY]` | change a story |
| `remove ID` | remove a story |
| `fmt [ROLE]...` | rewrite story files in the strict format |
| `check [--no-duplicates] [--tests PATH]` | stories that need a test and have none, tests that cite no existing story, duplicate ids; exits 1 on problems and prints the coverage per role |
| `check --missing`, `--covered`, `--stale` | only list the untested stories, the tested ones, or the tests that cite no existing story |

A vitest or playwright test cites a story by its title,
`test("student: log in", ...)`; a pytest test with
`@pytest.mark.story("student: log in")`. r2 reads the test files and runs no
test runner. E2e tests live in `test/stories` or `tests/stories`, or where
the project manifest (`r2.toml` or `[tool.r2]`) says:

```toml
[config.stories]
dir = "docs/user-stories"
tests = ["e2e"]
```

**`r2 roadmap`, `r2 changelog`**

Generate files from the `milestone` key of the issues in `dev/issues`, the
only source of the plan (format in `dev/spec/roadmap.md`).

| Command | Does |
| --- | --- |
| `roadmap` | write `ROADMAP.md`: the open issues grouped by milestone, milestones in version order (`0.9.0` before `0.10.0`) |
| `roadmap --check` | write nothing; exit 1 when `ROADMAP.md` is missing or out of date, for the lint step |
| `changelog --draft MILESTONE` | print the completed issues of the milestone under `Added` (enhancement), `Fixed` (defect) and `Other`, as a start for `CHANGELOG.md` |

Issues without a milestone stay out of the roadmap. The issue titles are
copied as written.

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
  `r2 --agent -v <command>` disables the reduction.
- Commands marked `destructive` refuse to run without `r2 --yes`.
- Output is plain text, even on a terminal: no colors, no boxes in `--help`
  and usage errors, and standard Python tracebacks. This covers plugin
  commands too. r2 also sets `NO_COLOR=1`, so the programs it runs print
  plain text as well.

### Setting up Claude Code

Claude Code applies the `env` table of its settings to every command it
runs, so one entry turns on agent mode and signs the agent's comments. Put
it in `.claude/settings.json` to share it with the project, in
`.claude/settings.local.json` to keep it to yourself, or in
`~/.claude/settings.json` for every project:

```json
{
  "env": {
    "R2_AGENT": "1",
    "R2_AUTHOR": "claude"
  }
}
```

Other agents need the same two variables in the environment of the shell
they run commands in.

## Global options

| Option | Meaning |
| --- | --- |
| `--agent` | agent mode |
| `-v`, `--verbose` | more output, repeatable |
| `-q`, `--quiet` | less output, repeatable |
| `-y`, `--yes` | pre-approve destructive commands |
| `--json` | JSON output for commands that read data |
| `-C <dir>` | run as if r2 started in dir |

Verbosity is a number: 0 for humans and -1 for agents, plus one per `-v`,
minus one per `-q`. At -1 project commands print a summary, at -2 only
errors, at 1 also the command they run, and at 2 debug logs.

Global options work after the command name too (`r2 glossary list --json`),
except `-C`, and except for project and plugin commands, which forward their
arguments: `r2 -q test -v` runs the tests quietly and passes `-v` to the
test runner. Errors go to stderr; the exit code is 1 for a failed command
and 2 for a usage error.

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

Command functions are ordinary Typer commands. Print through
`plugin.console` (stdout) and `plugin.err` (stderr), and read
`plugin.mode` for the verbosity and `--json`, instead of creating Rich
consoles of your own: agent mode swaps those consoles for plain ones, so
the plugin's output matches the rest of r2.

```python
@plugin.command()
def status() -> None:
    """Show what is mounted."""
    if plugin.mode.verbosity >= 0:
        plugin.console.print("[b]mounted[/]: /mnt/hd")
```

Only `plugin.toml` is read at
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

R2 has seven tabs. Each one has a drawer on the left and content on the
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
   Buttons under the issue move it to the next status of the workflow
   (backlog → todo → in progress → completed, blocked → deferred → wont fix,
   in review → completed, closed → backlog), edit its tags or delete it.
5. **ADRs**: the architecture decision records in `dev/adr`, grouped by
   status, with the same filter and comment thread as Issues. Press `n` to
   name a new decision; r2 writes `NNNN-slug.md` with the next number and the
   MADR sections, and opens it in the editor. The format is described in
   `dev/spec/adrs.md`. Buttons under the ADR move it between proposed,
   accepted and rejected, edit its tags, record which older ADR it supersedes
   (both files are updated) or delete it. `relatedTo`, `supersedes` and
   `supersededBy` entries open the files they name.
6. **RFCs**: the feature designs in `dev/rfc`, grouped by status, with the
   same filter and comment thread as Issues. Press `n` to name the feature
   to design; r2 writes `slug.md` with the Problem, Proposal, Alternatives,
   Open questions and Outcome sections, and opens it in the editor. The
   format is described in `dev/spec/rfcs.md`. Buttons under the RFC move it
   from draft to accepted or rejected, edit its tags or delete it; `s` also
   offers withdrawn. Leaving draft dates the decision.
7. **Glossary**: the terms of `GLOSSARY.md`, grouped by their `tags`. `/`
   filters the terms by any word of their name, definition or fields, so
   typing a word to avoid finds the term to use instead. A term shows its
   definition under a bar with its fields; `related` entries jump to the
   terms they name. Press `n` to add a term, which opens the file in the
   editor on it, and `e` to edit the term on display. The format is
   described in `dev/spec/glossary.md`.

When a reference has a line range, the preview shows an excerpt around it.
Press `f` to switch between the excerpt and the whole file. Images are shown
inline when the terminal supports it.

The top bar shows the project, its git branch, and whether the worktree is
clean, has staged changes or has unstaged changes. Click the `⭘` icon on its
left to open the command palette, where you can also change the theme.

The `‹` and `›` arrows at its right end go back and forward through the places
you visited, across tabs, like a browser. Tab switches, documents picked in a
tree and links followed count as visits; moving the cursor does not. Each
project has its own history, and an arrow dims when it has nowhere to go.

### Keys

| Key | Action |
| --- | --- |
| `1` to `7` | Switch to a view |
| `←` `→` | Move between drawer and content, then to the previous or next view |
| `f` | Toggle excerpt and whole file (Live view) |
| `e` | Edit the current file in the editor |
| `o` | Open the current file in its default application |
| `i` | Open the project in the GUI editor |
| `t` | Open a shell in the project root |
| `$` | Run a shell command in the project root and show its output |
| `p` | Pin the current project instead of following herdr focus |
| `n` | Create an issue, an ADR, an RFC or a glossary term |
| `c` | Comment on the issue, ADR or RFC on display (Issues, ADRs and RFCs views) |
| `s` | Change the status of the issue, ADR or RFC on display (Issues, ADRs and RFCs views) |
| `/` | Search the file or document on display; in the Issues, ADRs, RFCs and Glossary trees, filter them |
| `↑` `↓` | During a search, go to the previous or next match |
| `Esc` | Clear the search |
| `ctrl+shift+c` | Copy the selection in a file preview, where the terminal passes the key on |
| `F5` | Read the file on display and the git status again |
| `q` | Quit |

In the trees, `→` expands a node (in the Project tree, it opens a file) and `←`
folds an open node or goes up to its parent before leaving the tree.

### Configuration

R2 picks the programs it launches from the environment:

- `e` runs `$R2_EDITOR`, `editor` under `[r2]` in `~/.config/r2/config.toml`,
  `$EDITOR` or `$VISUAL`, falling back to `micro`.
  It passes `+LINE` to jump to the reference. VS Code and its forks get
  `--goto PATH:LINE` instead and start in their own window, without a wait
  flag such as `-w`, so r2 stays usable; r2 reads the files again when you
  come back to it.
- `i` runs `$R2_IDE`, `ide` under `[r2]` in the same file or `$VISUAL`,
  falling back to `code`.
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