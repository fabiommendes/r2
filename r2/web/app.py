"""
The HTTP API, the event stream and the UI shell.

One app serves every attached project. The API needs the bearer token; the
UI shell does not, because it carries no repository data, and refusing it
would leave a user with an expired cookie staring at a 401.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import mimetypes
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from pydantic import TypeAdapter
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import (
    FileResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.types import ASGIApp

from r2.core.reports.candidates import detect_candidates
from r2.core.reports.model import FileFact, RenderedReport, Resolutions, ReviewMarks
from r2.core.reports.project import Project
from r2.core.reports.refs import normalize_repo_path
from r2.core.reports.render import render_markdown
from r2.core.reports.scan import (
    SourceFile,
    list_source_files,
    read_source_file,
    stat_files,
)
from r2.core.reports.store import (
    ReportDocument,
    ReportStore,
    parse_marks,
    safe_report_path,
)
from r2.web.registry import load_projects
from r2.web.security import (
    DEFAULT_HOSTNAMES,
    TOKEN_COOKIE,
    OriginGuard,
    presented_token,
    same_token,
)
from r2.web.watch import WatchEvent, watch_reports
from r2.web.wire import (
    Health,
    LineLink,
    MarksEvent,
    ProjectsEvent,
    Reloaded,
    ReportEvent,
    ReportRemovedEvent,
    WireDocument,
    WireEvent,
    WireFile,
    WireFileEntry,
    WireProject,
    WireSummary,
    iso,
)

__all__ = ["Viewer"]

#: Seconds between heartbeats on an idle stream, so a proxy or a sleeping
#: laptop does not drop it.
HEARTBEAT = 25.0

ONE_YEAR = 60 * 60 * 24 * 365


@dataclass(eq=False)
class Context:
    project: Project
    store: ReportStore
    subscribers: set[asyncio.Queue[WireEvent | None]] = field(default_factory=set)
    watcher: asyncio.Task[None] | None = None


class Viewer:
    """
    The served set of projects, and the ASGI app over them.

    `asgi` is what a server runs: the FastAPI app behind the origin guard.
    """

    def __init__(
        self,
        projects: Iterable[Project],
        token: str,
        *,
        static_root: Path | None = None,
        hostnames: Iterable[str] = DEFAULT_HOSTNAMES,
        watch: bool = True,
    ) -> None:
        self.token = token
        self.watch = watch
        self.contexts: dict[str, Context] = {}
        for project in projects:
            self.contexts[project.id] = Context(project, ReportStore(project))
        self.app = build_app(self, static_root)
        self.asgi: ASGIApp = OriginGuard(self.app, hostnames)

    async def start(self) -> None:
        """Start the watchers. Needs a running event loop."""
        for context in self.contexts.values():
            self._watch(context)

    async def sync(self, projects: Iterable[Project]) -> None:
        """
        Make the served set match projects, adding and dropping watchers.
        This is how a project attached in another terminal shows up in a
        daemon that is already running.
        """
        wanted = {project.id: project for project in projects}
        changed = False
        for project_id in [key for key in self.contexts if key not in wanted]:
            await self._drop(self.contexts.pop(project_id))
            changed = True
        for project_id, project in wanted.items():
            if project_id not in self.contexts:
                context = Context(project, ReportStore(project))
                self.contexts[project_id] = context
                self._watch(context)
                changed = True
        if changed:
            self.broadcast(ProjectsEvent())

    def broadcast(self, event: WireEvent) -> None:
        """Send an event to the subscribers of its project, or to all."""
        if isinstance(event, ProjectsEvent):
            targets = list(self.contexts.values())
        else:
            context = self.contexts.get(event.project)
            targets = [] if context is None else [context]
        for context in targets:
            for queue in context.subscribers:
                queue.put_nowait(event)

    async def close(self) -> None:
        for context in self.contexts.values():
            await self._drop(context)
        self.contexts.clear()

    def _watch(self, context: Context) -> None:
        if not self.watch or context.watcher is not None:
            return

        def on_event(event: WatchEvent) -> None:
            context.store.forget(event.path)
            project = context.project.id
            wire: WireEvent
            if event.kind == "marks":
                wire = MarksEvent(project=project, path=event.path)
            elif event.kind == "report":
                wire = ReportEvent(project=project, path=event.path)
            else:
                wire = ReportRemovedEvent(project=project, path=event.path)
            self.broadcast(wire)

        context.watcher = asyncio.create_task(
            _keep_watching(context.project, on_event),
            name=f"watch {context.project.id}",
        )

    async def _drop(self, context: Context) -> None:
        for queue in context.subscribers:
            queue.put_nowait(None)
        context.subscribers.clear()
        if context.watcher is not None:
            context.watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await context.watcher
            context.watcher = None


async def _keep_watching(project: Project, on_event: Any) -> None:
    """A watcher error must not take the daemon down: wait and watch again."""
    while True:
        with contextlib.suppress(OSError, RuntimeError):
            await watch_reports(project, on_event)
        await asyncio.sleep(1.0)


def build_app(viewer: Viewer, static_root: Path | None) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await viewer.start()
        try:
            yield
        finally:
            await viewer.close()

    app = FastAPI(
        title="r2 web",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.viewer = viewer

    @app.exception_handler(StarletteHTTPException)
    async def plain_errors(
        _request: Request, error: StarletteHTTPException
    ) -> Response:
        return PlainTextResponse(f"{error.detail}\n", error.status_code)

    @app.get("/auth", include_in_schema=False)
    def auth(token: str = "", to: str = "/") -> Response:
        """How the browser gets the token: `r2 web` opens this URL."""
        if not same_token(token, viewer.token):
            return PlainTextResponse("unauthorized\n", 401)
        # Never off-site: `//evil.example` is a path to a browser too.
        target = to if to.startswith("/") and not to.startswith("//") else "/"
        response = RedirectResponse(target, 302)
        response.set_cookie(
            TOKEN_COOKIE,
            token,
            max_age=ONE_YEAR,
            path="/",
            httponly=True,
            samesite="strict",
        )
        return response

    app.include_router(api_router(viewer), prefix="/api")
    if static_root is not None:
        mount_shell(app, static_root.resolve())
    app.openapi = lambda: openapi(app)  # type: ignore[method-assign]
    return app


def _viewer(request: Request) -> Viewer:
    viewer: Viewer = request.app.state.viewer
    return viewer


def _require_token(request: Request) -> None:
    presented = presented_token(
        request.headers.get("authorization"), request.headers.get("cookie")
    )
    if not same_token(presented, _viewer(request).token):
        raise HTTPException(401, "unauthorized")


def _context(request: Request, project: str) -> Context:
    context = _viewer(request).contexts.get(project)
    if context is None:
        raise HTTPException(404, "no such project")
    return context


def _report_path(path: str = "") -> str:
    safe = safe_report_path(path)
    if safe is None:
        raise HTTPException(400, "bad report path")
    return safe


type ProjectContext = Annotated[Context, Depends(_context)]
type ReportPath = Annotated[str, Depends(_report_path)]


def api_router(viewer: Viewer) -> APIRouter:
    api = APIRouter(dependencies=[Depends(_require_token)])

    @api.get("/health")
    def health() -> Health:
        return Health(ok=True, projects=len(viewer.contexts))

    @api.post("/reload")
    async def reload() -> Reloaded:
        """Re-read the registry. `r2 web` calls it after attaching a project."""
        loaded = await asyncio.to_thread(load_projects)
        await viewer.sync(loaded.projects)
        return Reloaded(projects=len(viewer.contexts))

    @api.get("/projects")
    def projects() -> list[WireProject]:
        return [
            WireProject(id=c.project.id, name=c.project.name, root=str(c.project.root))
            for c in viewer.contexts.values()
        ]

    @api.get("/p/{project}/reports", response_model_exclude_none=True)
    def reports(context: ProjectContext) -> list[WireSummary]:
        return [WireSummary.of(summary) for summary in context.store.summaries()]

    @api.get("/p/{project}/report", response_model_exclude_none=True)
    def report(context: ProjectContext, path: ReportPath) -> WireDocument:
        document = context.store.read(path)
        if document is None:
            raise HTTPException(404, "no such report")
        return WireDocument.of(
            document,
            context.store.read_marks(path),
            resolve_references(document, context.project.root),
        )

    @api.get("/p/{project}/files")
    def files(context: ProjectContext) -> list[WireFileEntry]:
        return [
            WireFileEntry.of(entry) for entry in list_source_files(context.project.root)
        ]

    @api.get(
        "/p/{project}/file",
        response_model_exclude_none=True,
        responses={415: {"description": "Not a text file"}},
    )
    def file(context: ProjectContext, path: str = "") -> WireFile:
        """
        A file of the working tree. This route serves the user's repository
        to a browser, so the path is checked twice: for its shape here, and
        against a symlink that leaves the project in `confine`.
        """
        normal = normalize_repo_path(path)
        if not normal:
            raise HTTPException(400, "bad file path")
        result = read_source_file(context.project.root, normal)
        if result == "binary":
            raise HTTPException(415, "not a text file")
        if result == "missing":
            raise HTTPException(404, "no such file")
        return file_view(result, context.project.root)

    @api.put(
        "/p/{project}/marks",
        response_model_exclude_none=True,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ReviewMarks"}
                    }
                },
            }
        },
    )
    async def marks(
        request: Request, context: ProjectContext, path: ReportPath
    ) -> ReviewMarks:
        """Lenient: anything unrecognized in the body is dropped."""
        if await asyncio.to_thread(context.store.read, path) is None:
            raise HTTPException(404, "no such report")
        try:
            body = json.loads(await request.body())
        except ValueError:
            raise HTTPException(400, "body is not JSON") from None
        parsed = parse_marks(body)
        await asyncio.to_thread(context.store.write_marks, path, parsed)
        viewer.broadcast(MarksEvent(project=context.project.id, path=path))
        return parsed

    @api.get(
        "/p/{project}/stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Server-sent events, one `WireEvent` per frame.",
                "content": {"text/event-stream": {}},
            }
        },
    )
    async def stream(context: ProjectContext) -> StreamingResponse:
        return StreamingResponse(
            events(context),
            media_type="text/event-stream",
            headers={"cache-control": "no-store"},
        )

    return api


async def events(context: Context) -> AsyncIterator[str]:
    queue: asyncio.Queue[WireEvent | None] = asyncio.Queue()
    context.subscribers.add(queue)
    try:
        yield _frame("ready", "{}")
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), HEARTBEAT)
            except TimeoutError:
                yield _frame("ping", "{}")
                continue
            if event is None:
                return
            yield _frame(event.type, event.model_dump_json(exclude_none=True))
    finally:
        context.subscribers.discard(queue)


def _frame(name: str, data: str) -> str:
    return f"event: {name}\ndata: {data}\n\n"


def resolve_references(document: ReportDocument, root: Path) -> Resolutions:
    """
    Phase two of reference detection: one batched `stat` of the working tree.
    The render step only finds candidates and decides nothing, since it does
    no I/O; a path with no entry here renders as plain text.
    """
    return _resolve(_wanted(document.rendered), root, document.modified.timestamp())


def file_view(file: SourceFile, root: Path) -> WireFile:
    """A file with its Markdown rendered and the paths in its lines linked."""
    rendered = (
        render_markdown("\n".join(file.lines)) if is_markdown(file.path) else None
    )
    wanted = _wanted(rendered) if rendered is not None else set()
    found: list[LineLink] = []
    for number, text in enumerate(file.lines, start=1):
        for candidate in detect_candidates(text):
            if candidate.kind != "path" or candidate.path is None:
                continue
            wanted.add(candidate.path)
            found.append(
                LineLink(
                    line=number,
                    start=_utf16(text, candidate.start),
                    end=_utf16(text, candidate.end),
                    candidate=candidate,
                )
            )
    resolutions = _resolve(wanted, root, file.modified.timestamp())
    links = [link for link in found if link.candidate.path in resolutions]
    return WireFile.of(file, rendered, links, resolutions)


def is_markdown(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.upper() in ("README", "README.MD") or name.lower().endswith(
        (".md", ".mdx")
    )


def _wanted(rendered: RenderedReport) -> set[str]:
    wanted = {ref.path for ref in rendered.refs}
    for candidate in rendered.candidates:
        if candidate.kind == "path" and candidate.path is not None:
            wanted.add(candidate.path)
    return wanted


def _resolve(wanted: set[str], root: Path, written: float) -> Resolutions:
    if not wanted:
        return {}
    resolutions: Resolutions = {}
    for path, stat in stat_files(root, sorted(wanted)).items():
        # The only staleness signal in the product, and deliberately not git.
        changed = stat.modified.timestamp() > written
        resolutions[path] = FileFact(
            path=path, modified=iso(stat.modified), changed=changed or None
        )
    return resolutions


def _utf16(text: str, offset: int) -> int:
    return len(text[:offset].encode("utf-16-le")) // 2


def mount_shell(app: FastAPI, root: Path) -> None:
    """
    Serve the built UI, falling back to `index.html` so client-side routes
    work. The bundle is content hashed; `index.html` is never cached.
    """
    index = root / "index.html"

    @app.get("/{rest:path}", include_in_schema=False)
    def shell(rest: str) -> Response:
        target = (root / rest).resolve() if "\0" not in rest else index
        if not target.is_relative_to(root) or not target.is_file():
            target = index
        if not target.is_file():
            return PlainTextResponse("not found\n", 404)
        if target == index:
            return FileResponse(index, headers={"cache-control": "no-store"})
        kind, _ = mimetypes.guess_type(target.name)
        return FileResponse(
            target,
            media_type=kind or "application/octet-stream",
            headers={"cache-control": "public, max-age=31536000, immutable"},
        )


def openapi(app: FastAPI) -> dict[str, Any]:
    """The API schema, plus the stream's event models as components."""
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    event = TypeAdapter[WireEvent](WireEvent).json_schema(
        mode="serialization", ref_template="#/components/schemas/{model}"
    )
    components.update(event.pop("$defs", {}))
    components["WireEvent"] = event
    app.openapi_schema = schema
    return schema
