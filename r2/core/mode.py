"""
Global run mode, set once from the root `r2` options.

The flags live here, outside the CLI layer, so that plugins and library code
can consult them without importing Typer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = ["Mode", "mode", "configure"]

AGENT_ENV = "R2_AGENT"


@dataclass
class Mode:
    #: Agent mode: no prompts, terse output, destructive commands need --yes.
    agent: bool = False
    #: Disable output reduction in agent mode (passthrough everything).
    full: bool = False
    #: Pre-approve destructive commands.
    yes: bool = False

    @property
    def summarize(self) -> bool:
        """
        Whether command output should be reduced to a summary.
        """
        return self.agent and not self.full


mode = Mode()


def configure(agent: bool = False, full: bool = False, yes: bool = False) -> Mode:
    """
    Set the global mode. Called from the root CLI callback.

    `R2_AGENT=1` in the environment also enables agent mode, so an agent's
    shell can turn it on once instead of passing `--agent` to every call.
    """
    mode.agent = agent or env_flag(AGENT_ENV)
    mode.full = full
    mode.yes = yes
    return mode


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
