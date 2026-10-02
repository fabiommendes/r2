R2 is a personal computer assistant with two faces:

- a **TUI**, a sidekick for Claude Code. Run `r2` with no arguments in a
  terminal split next to [herdr](https://herdr.dev);
- a **command line** of small chores: `r2 hd`, `r2 alias`, `r2 glossary` and
  the project commands `r2 test`, `r2 build` and `r2 docs`.

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
`~/.config/robin/config.json` to the new config path if there is no r2 config
yet. `ROBIN_EDITOR` and `ROBIN_IDE` are now `R2_EDITOR` and `R2_IDE`.

## Commands

`r2` with no arguments opens the TUI. With arguments, it runs one of these
commands.

**`r2 hd <PATH>`**

Move a file or directory to the hard drive path and leave a symlink behind.
My setup has a hard drive mounted at `~/hd`, and I use this command to move
files there when I want to free up space on my main SSD drive. The path comes
from `~/.config/r2/config.toml`, which r2 creates on first use:

```toml
[hd]
path = "~/hd"
```

**`r2 alias <ALIAS> <COMMAND>`**

Create a shell alias. This is useful for creating shortcuts for commands I use
often. The setup assumes the existence of a file `~/.bash_aliases` where these
aliases are stored. It also assumes the file has a specific format, with a
section for R2 aliases that looks like this:

```sh
# R2 Aliases
alias ll='ls -la'
alias gs='git status'
```

`r2 alias` will add a new alias to some specific section (or the fallback
"other", if not given). It will also check for duplicates before adding a new
alias. It also has special support for aliasing Python packages (using uv,
with `--py`) or Javascript packages (using npx, with `--js`). Use `--list` or
`--sections` to see what is there, and `--edit` to open the file in your
editor.

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
`$XDG_CONFIG_HOME/r2/config.json` (`~/.config/r2/config.json` by
default):

```json
{
  "drawer_widths": {"live": 30, "project": 40, "docs": 30, "issues": 30},
  "theme": "nord"
}
```

A missing or broken file falls back to the defaults.
