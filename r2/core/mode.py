"""
Global run mode, set once from the root `r2` options.

The flags live here, outside the CLI layer, so that plugins and library code
can consult them without importing Typer. See dev/spec/cli.md.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

__all__ = [
    "DEBUG",
    "NORMAL",
    "SILENT",
    "SUMMARY",
    "VERBOSE",
    "Mode",
    "configure",
    "mode",
]

AGENT_ENV = "R2_AGENT"

#: Verbosity levels; commands clamp mode.verbosity to the ones they support.
SILENT = -2
SUMMARY = -1
NORMAL = 0
VERBOSE = 1
DEBUG = 2


@dataclass
class Mode:
    #: Agent mode: no prompts, summary output, destructive commands need --yes.
    agent: bool = False
    #: The mode default (0 for humans, -1 for agents), plus -v, minus -q.
    verbosity: int = NORMAL
    #: Pre-approve destructive commands.
    yes: bool = False
    #: Print data as JSON in commands that read it.
    json: bool = False

    @property
    def summarize(self) -> bool:
        """
        Whether command output should be reduced to a summary.
        """
        return self.verbosity < NORMAL


mode = Mode()


def configure(
    agent: bool = False,
    verbose: int = 0,
    quiet: int = 0,
    yes: bool = False,
    json: bool = False,
) -> Mode:
    """
    Set the global mode. Called from the root CLI callback.

    `R2_AGENT=1` in the environment also enables agent mode, so an agent's
    shell can turn it on once instead of passing `--agent` to every call.
    """
    mode.agent = agent or env_flag(AGENT_ENV)
    mode.verbosity = (SUMMARY if mode.agent else NORMAL) + verbose - quiet
    mode.yes = yes
    mode.json = json
    if mode.verbosity >= DEBUG:
        logging.basicConfig(level=logging.DEBUG)
    return mode


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
