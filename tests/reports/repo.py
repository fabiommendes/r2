"""
A throwaway repository with an attached `.reportlab/`, shared by the report
and web tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from r2.core.reports.project import REPORT_SUFFIX, Project, describe, ensure_layout


@dataclass(frozen=True)
class Repo:
    project: Project

    @classmethod
    def create(cls, root: Path) -> Repo:
        """A directory with a `.git` folder and a real, attached `.reportlab/`."""
        (root / ".git").mkdir(parents=True)
        ensure_layout(describe(root))
        return cls(describe(root))

    @property
    def root(self) -> Path:
        return self.project.root

    def write_report(self, path: str, text: str) -> Path:
        """Write a report. `path` has no extension; folders are created."""
        file = self.project.reports.joinpath(*f"{path}{REPORT_SUFFIX}".split("/"))
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
        return file

    def write_file(self, path: str, content: str | bytes) -> Path:
        """Write any file, relative to the repository root."""
        file = self.root.joinpath(*path.split("/"))
        file.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            file.write_bytes(content)
        else:
            file.write_text(content, encoding="utf-8")
        return file


def set_mtime(file: Path, seconds: float) -> None:
    """Pin a modification time, so ordering never depends on the clock."""
    os.utime(file, (seconds, seconds))
