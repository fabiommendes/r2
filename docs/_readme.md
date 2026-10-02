Robin is a sidekick TUI for Claude Code. Run it in a terminal split next to
[herdr](https://herdr.dev): it follows the herdr pane in focus and shows what
the Claude session in that pane is doing, including the files it reads and the
`path/to/file.py:20-56` references it mentions in its answers.

## Installation

```bash
uv tool install robin-tui
```

This installs two commands: `robin`, the TUI, and `robin-notify`, the Claude
Code hook that feeds it.

## Setup

Register the hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {"matcher": "Read|Edit|Write", "hooks": [{"type": "command", "command": "robin-notify"}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "command": "robin-notify"}]}
    ]
  }
}
```

Then split your terminal, run `herdr` on one side and `robin` on the other.

The hook appends each event to `$XDG_STATE_HOME/robin/events.jsonl`
(`~/.local/state/robin/events.jsonl` by default), so robin picks up what
happened even if it was not running at the time. Without herdr, robin shows
the project of the directory it was started in.

## Views

Robin has four tabs. Each one has a drawer on the left and content on the
right. Drag the bar between them to resize the drawer.

1. **Live**: the files Claude read and the references it wrote in its last
   answers, newest first, with a preview of the selected one.
2. **Project**: the project tree, without the files git ignores, and a
   preview of the selected file.
3. **Docs**: the Markdown files in `dev/docs`, `dev/spec` and `docs`. The
   frontmatter shows in a bar above the document instead of in the text.
4. **Issues**: the issues in `dev/issues`, grouped by status. Closed issues
   are hidden until you press `a`; `/` filters by title, tags and other
   metadata. Comments show as a thread of collapsible cards. Press `n` to fill
   in a form with the metadata of a new issue; robin writes the file and opens
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
| `a` | Show or hide closed issues (Issues view) |
| `/` | Filter the issues (Issues view) |
| `q` | Quit |

In the Project tree, `→` expands a folder or opens a file, and `←` collapses
a folder or goes up to the parent folder.

## Configuration

Robin picks the programs it launches from the environment:

- `e` runs `$ROBIN_EDITOR`, `$EDITOR` or `$VISUAL`, falling back to `micro`.
  It passes `+LINE` to jump to the reference.
- `i` runs `$ROBIN_IDE` or `$VISUAL`, falling back to `code`.
- `t` runs `$SHELL`.

Robin saves the theme and the width of each drawer in
`$XDG_CONFIG_HOME/robin/config.json` (`~/.config/robin/config.json` by
default):

```json
{
  "drawer_widths": {"live": 30, "project": 40, "docs": 30, "issues": 30},
  "theme": "nord"
}
```

A missing or broken file falls back to the defaults.
