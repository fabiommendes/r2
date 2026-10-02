# robin

[![CI](https://github.com/fabiommendes/robin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/fabiommendes/robin/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/robin-tui.svg)](https://pypi.org/project/robin-tui/)

Robin is a sidekick TUI for Claude Code. Run it in a terminal split next to
[herdr](https://herdr.dev): it follows the herdr pane in focus and shows what
the Claude session in that pane is doing, including the files it reads and
edits and the `path/to/file.py:20-56` references it mentions in its answers.

## Installation

```bash
uv tool install robin-tui
```

This installs two commands: `robin`, the TUI, and `robin-notify`, the Claude
Code hook that feeds it.

## Usage

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
