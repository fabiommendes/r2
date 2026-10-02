R2 is a sidekick TUI for Claude Code. Run it in a terminal split next to
[herdr](https://herdr.dev): it follows the herdr pane in focus and shows what
the Claude session in that pane is doing, including the files it reads and the
`path/to/file.py:20-56` references it mentions in its answers.

## Installation

```bash
uv tool install r2-assistant
```

This installs two commands: `r2`, the TUI, and `r2-notify`, the Claude
Code hook that feeds it.

R2 used to be called robin. `robin-notify` still works as an alias of
`r2-notify`, so existing hook settings keep working, but point them to
`r2-notify` when you can. The first run copies `~/.config/robin/config.json`
to the new config path if there is no r2 config yet. `ROBIN_EDITOR` and
`ROBIN_IDE` are now `R2_EDITOR` and `R2_IDE`.

## Setup

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

## Views

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

## Keys

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

## Configuration

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
