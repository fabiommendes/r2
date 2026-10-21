"""
The shape of the HTTP API and the event stream.

The browser's TypeScript types are generated from the OpenAPI schema of
these models (`web/src/api.gen.ts`), so this module is the contract. Times are
ISO 8601 strings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from r2.core.reports.model import (
    Candidate,
    Frontmatter,
    RenderedReport,
    Resolutions,
    ReviewMarks,
    Severity,
    Wire,
)
from r2.core.reports.scan import FileStat, SourceFile
from r2.core.reports.store import ReportDocument, ReportSummary

__all__ = [
    "Health",
    "LineLink",
    "Reloaded",
    "WireDocument",
    "WireEvent",
    "WireFile",
    "WireFileEntry",
    "WireProject",
    "WireSummary",
]


def iso(moment: datetime) -> str:
    return moment.isoformat()


class Health(Wire):
    ok: bool
    projects: int


class Reloaded(Wire):
    projects: int


class WireProject(Wire):
    id: str
    name: str
    root: str


class WireSummary(Wire):
    path: str
    title: str
    kind: str
    tags: list[str]
    modified: str
    findings: int
    severity: Severity | None = None
    open: bool
    read: str | None = None

    @classmethod
    def of(cls, summary: ReportSummary) -> WireSummary:
        return cls(
            path=summary.path,
            title=summary.title,
            kind=summary.kind,
            tags=summary.tags,
            modified=iso(summary.modified),
            findings=summary.findings,
            severity=summary.severity,
            open=summary.open,
            read=summary.read,
        )


class WireDocument(Wire):
    path: str
    title: str
    kind: str
    tags: list[str]
    modified: str
    frontmatter: Frontmatter
    rendered: RenderedReport
    #: Absent when the human never marked anything.
    marks: ReviewMarks | None = None
    #: Which of the report's references are files on disk, keyed by path.
    resolutions: Resolutions

    @classmethod
    def of(
        cls,
        document: ReportDocument,
        marks: ReviewMarks | None,
        resolutions: Resolutions,
    ) -> WireDocument:
        return cls(
            path=document.path,
            title=document.title,
            kind=document.kind,
            tags=document.tags,
            modified=iso(document.modified),
            frontmatter=document.frontmatter,
            rendered=document.rendered,
            marks=marks,
            resolutions=resolutions,
        )


class WireFileEntry(Wire):
    path: str
    modified: str
    size: int

    @classmethod
    def of(cls, entry: FileStat) -> WireFileEntry:
        return cls(path=entry.path, modified=iso(entry.modified), size=entry.size)


class LineLink(Wire):
    """
    A path cited in a line of a file, that is a file on disk. Offsets count
    UTF-16 code units, as JavaScript strings do.
    """

    #: 1-based line number.
    line: int
    start: int
    end: int
    candidate: Candidate


class WireFile(Wire):
    """One file of the working tree, ready to render."""

    path: str
    modified: str
    size: int
    hash: str
    lines: list[str]
    #: Shiki language id. Absent when there is no grammar for the file.
    lang: str | None = None
    truncated: bool | None = None
    #: The rendered document, for a Markdown file.
    rendered: RenderedReport | None = None
    #: Paths cited in the lines that are files on disk.
    links: list[LineLink]
    #: Files the rendered document and the links point to.
    resolutions: Resolutions

    @classmethod
    def of(
        cls,
        file: SourceFile,
        rendered: RenderedReport | None,
        links: list[LineLink],
        resolutions: Resolutions,
    ) -> WireFile:
        return cls(
            path=file.path,
            modified=iso(file.modified),
            size=file.size,
            hash=file.hash,
            lines=file.lines,
            lang=file.lang,
            truncated=file.truncated or None,
            rendered=rendered,
            links=links,
            resolutions=resolutions,
        )


class ReportEvent(Wire):
    type: Literal["report"] = "report"
    project: str
    path: str


class ReportRemovedEvent(Wire):
    type: Literal["report-removed"] = "report-removed"
    project: str
    path: str


class MarksEvent(Wire):
    type: Literal["marks"] = "marks"
    project: str
    path: str


class ProjectsEvent(Wire):
    type: Literal["projects"] = "projects"


#: One frame of `/api/p/{id}/stream`. The SSE event name is `type`, and the
#: data is the event as JSON.
type WireEvent = Annotated[
    ReportEvent | ReportRemovedEvent | MarksEvent | ProjectsEvent,
    Field(discriminator="type"),
]
