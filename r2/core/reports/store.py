"""
Reads `.reportlab/reports/` and the review marks beside each report.

Nothing here is authoritative except the files themselves. Review marks are
written beside the report they belong to, which gives them the report's
lifetime.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from r2.core.files import atomic_write
from r2.core.reports.frontmatter import parse_document, title_from_path
from r2.core.reports.model import (
    SEVERITIES,
    FindingMark,
    Frontmatter,
    RenderedReport,
    ReviewMarks,
    Severity,
)
from r2.core.reports.project import REPORT_SUFFIX, REVIEW_SUFFIX, Project
from r2.core.reports.render import render_markdown

__all__ = [
    "ReportDocument",
    "ReportStore",
    "ReportSummary",
    "parse_marks",
    "safe_report_path",
]


@dataclass(frozen=True)
class ReportDocument:
    #: Path under `reports/` with no extension. The report's identity.
    path: str
    title: str
    kind: str
    tags: list[str]
    modified: datetime
    frontmatter: Frontmatter
    rendered: RenderedReport


@dataclass(frozen=True)
class ReportSummary:
    path: str
    title: str
    kind: str
    tags: list[str]
    modified: datetime
    findings: int
    #: An unterminated block: the agent is probably still writing.
    open: bool
    #: Highest severity among the findings, None when there are none.
    severity: Severity | None = None
    #: When the human last opened it, from the sidecar.
    read: str | None = None


@dataclass
class ReportStore:
    """
    Parsed documents are cached in memory, keyed by size and modification
    time: parsing a report is cheap and nothing here needs to survive a
    restart.
    """

    project: Project
    _cache: dict[str, tuple[tuple[int, int], ReportDocument]] = field(
        default_factory=dict, repr=False
    )

    def summaries(self) -> list[ReportSummary]:
        """Every report, newest first."""
        summaries = [
            self._summarize(document)
            for path in self._paths()
            if (document := self.read(path)) is not None
        ]
        summaries.sort(key=lambda summary: summary.modified, reverse=True)
        return summaries

    def read(self, path: str) -> ReportDocument | None:
        file = self._file_for(path, REPORT_SUFFIX)
        if file is None:
            return None
        try:
            stat = file.stat()
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Deleted between the watcher event and this read, which is routine.
            self._cache.pop(path, None)
            return None
        key = (stat.st_size, stat.st_mtime_ns)
        cached = self._cache.get(path)
        if cached is not None and cached[0] == key:
            return cached[1]
        document = _build(
            path, text, datetime.fromtimestamp(stat.st_mtime).astimezone()
        )
        self._cache[path] = (key, document)
        return document

    def read_marks(self, path: str) -> ReviewMarks | None:
        file = self._file_for(path, REVIEW_SUFFIX)
        if file is None:
            return None
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return parse_marks(raw)

    def write_marks(self, path: str, marks: ReviewMarks) -> None:
        """Written in one step, so no watcher sees a partial file."""
        file = self._file_for(path, REVIEW_SUFFIX)
        if file is None:
            raise ValueError(f"report path escapes the project: {path}")
        data = marks.model_dump(mode="json", exclude_none=True)
        atomic_write(file, json.dumps(data, indent=2) + "\n")

    def forget(self, path: str) -> None:
        self._cache.pop(path, None)

    def _summarize(self, document: ReportDocument) -> ReportSummary:
        marks = self.read_marks(document.path)
        return ReportSummary(
            path=document.path,
            title=document.title,
            kind=document.kind,
            tags=document.tags,
            modified=document.modified,
            findings=len(document.rendered.findings),
            open=document.rendered.open is True,
            severity=_highest_severity(document.rendered),
            read=marks.read if marks is not None else None,
        )

    def _paths(self) -> list[str]:
        """Every `.md` under `reports/`, as report paths."""
        found: list[str] = []
        root = self.project.reports
        for folder, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            prefix = Path(folder).relative_to(root).as_posix()
            for name in files:
                if name.startswith(".") or not name.endswith(REPORT_SUFFIX):
                    continue
                base = name.removesuffix(REPORT_SUFFIX)
                found.append(base if prefix == "." else f"{prefix}/{base}")
        return found

    def _file_for(self, path: str, suffix: str) -> Path | None:
        safe = safe_report_path(path)
        if safe is None:
            return None
        *folders, name = safe.split("/")
        return self.project.reports.joinpath(*folders, name + suffix)


def safe_report_path(path: str) -> str | None:
    """
    A report path is a relative POSIX path with no `..`, no hidden parts and
    no extension. Checked rather than trusted, because it arrives from a URL.
    """
    if "\0" in path:
        return None
    parts: list[str] = []
    for part in path.replace("\\", "/").split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts or any(part.startswith(".") for part in parts):
        return None
    return "/".join(parts)


def parse_marks(raw: object) -> ReviewMarks:
    """Coerce untrusted JSON into review marks, dropping anything unrecognized."""
    marks = ReviewMarks()
    if not isinstance(raw, dict):
        return marks
    if isinstance(read := raw.get("read"), str):
        marks.read = read
    findings = raw.get("findings")
    if not isinstance(findings, dict):
        return marks
    for key, value in findings.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        note = value.get("note")
        try:
            mark = FindingMark.model_validate(
                {
                    "state": value.get("state"),
                    "note": note if isinstance(note, str) else None,
                }
            )
        except ValidationError:
            continue
        marks.findings[key] = mark
    return marks


def _build(path: str, text: str, modified: datetime) -> ReportDocument:
    parsed = parse_document(text)
    rendered = render_markdown(parsed.body)
    rendered.diagnostics = [*parsed.diagnostics, *rendered.diagnostics]
    frontmatter = parsed.frontmatter
    return ReportDocument(
        path=path,
        title=(frontmatter.title or "").strip()
        or rendered.first_heading
        or title_from_path(path),
        kind=(frontmatter.kind or "").strip() or "note",
        tags=frontmatter.tags or [],
        modified=modified,
        frontmatter=frontmatter,
        rendered=rendered,
    )


def _highest_severity(rendered: RenderedReport) -> Severity | None:
    ranks = [SEVERITIES.index(finding.severity) for finding in rendered.findings]
    return SEVERITIES[min(ranks)] if ranks else None
