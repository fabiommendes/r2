#
# `r2 web`: the report viewer. See docs/reports.md.
#
from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

import typer

from r2.core.messages import error
from r2.core.reports.project import (
    Project,
    describe,
    detach_project,
    ensure_layout,
    find_project,
)

web_app = typer.Typer(
    help="Show the reports agents write into .reportlab/reports/ in the browser.",
    no_args_is_help=True,
)
browser_opt = typer.Option(
    "--browser/--no-browser", help="Open the browser, or only print the URL."
)


def _web() -> None:
    """Fail early, and helpfully, when the web extra is missing."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import watchfiles  # noqa: F401
    except ModuleNotFoundError:
        error("r2 web needs the web extra: uv tool install 'r2-assistant[web]'")


@web_app.command()
def init(browser: Annotated[bool, browser_opt] = True) -> None:
    """
    Attach this project and open it. The only command that writes into the
    repository: it creates .reportlab/ and its config file.
    """
    _web()
    from r2.web.registry import register

    found = find_project(Path.cwd())
    ensure_layout(found)
    project = describe(found.root)
    register(project)
    if project.config_error is not None:
        typer.echo(project.config_error, err=True)
    show(project, browser)


@web_app.command("open")
def open_(browser: Annotated[bool, browser_opt] = True) -> None:
    """
    Open this project in the browser. It must be attached: run `r2 web init`
    once.
    """
    _web()
    from r2.web.registry import read_registry, register

    project = find_project(Path.cwd())
    if not project.attached:
        error(f"{project.root} is not attached: run `r2 web init` here")
    if all(entry.id != project.id for entry in read_registry().projects):
        register(project)
    show(project, browser)


@web_app.command()
def detach(
    purge: Annotated[
        bool, typer.Option("--purge", help="Also delete .reportlab/ and its reports.")
    ] = False,
) -> None:
    """
    Stop watching this project. Deletes only .reportlab/config.toml, unless
    --purge.
    """
    _web()
    from r2.web.daemon import reload
    from r2.web.registry import unregister
    from r2.web.state import read_live_daemon_state

    project = find_project(Path.cwd())
    result = detach_project(project, purge=purge)
    unregister(project.id)
    if (state := read_live_daemon_state()) is not None:
        reload(state)
    if not result.detached and not result.purged:
        typer.echo(f"{project.root} was not attached")
        return
    typer.echo(f"detached {project.name}")
    if result.purged:
        plural = "report" if result.reports == 1 else "reports"
        typer.echo(f"deleted {project.reportlab} and {result.reports} {plural}")
    else:
        typer.echo(f"{project.reportlab} is untouched; `r2 web init` attaches again")


@web_app.command()
def serve(
    port: Annotated[int, typer.Option(help="Port to try first.")] = 7717,
) -> None:
    """
    Run the daemon in the foreground.
    """
    _web()
    from r2.web.daemon import serve as run

    def ready(state: object) -> None:
        from r2.web.state import DaemonState

        assert isinstance(state, DaemonState)
        typer.echo(f"listening on http://127.0.0.1:{state.port} (pid {state.pid})")

    if not run(port, on_ready=ready):
        typer.echo("a daemon is already running")


@web_app.command()
def stop() -> None:
    """
    Stop the running daemon.
    """
    _web()
    from r2.web.daemon import stop_daemon

    typer.echo("stopped" if stop_daemon() else "not running")


@web_app.command()
def status() -> None:
    """
    Show whether the daemon is up, and the projects it serves.
    """
    _web()
    from r2.web.daemon import reachable
    from r2.web.registry import read_registry
    from r2.web.state import read_live_daemon_state

    state = read_live_daemon_state()
    if state is None:
        typer.echo("daemon: not running")
    else:
        health = "ok" if reachable(state) else "not answering"
        typer.echo(f"daemon: pid {state.pid}, port {state.port}, {health}")

    entries = read_registry().projects
    if not entries:
        typer.echo("projects: none registered")
        return
    typer.echo("projects:")
    for entry in entries:
        # Described rather than printed from the registry, so the name
        # reflects config.toml and a folder that has moved says so.
        try:
            project = describe(Path(entry.root))
        except OSError:
            typer.echo(f"  {entry.name}  {entry.root}  (gone)")
            continue
        typer.echo(f"  {project.name}  {project.root}")
        if project.config_error is not None:
            typer.echo(f"    {project.config_error}")


@web_app.command()
def skill(
    install: Annotated[
        bool,
        typer.Option(
            "--install", help="Write it to .claude/skills/reportlab/SKILL.md."
        ),
    ] = False,
) -> None:
    """
    Print the skill that teaches agents to write reports, or install it.
    """
    source = Path(__file__).parent.parent / "web" / "skill" / "SKILL.md"
    if not install:
        typer.echo(source.read_text(encoding="utf-8"), nl=False)
        return
    project = find_project(Path.cwd())
    target = project.root / ".claude" / "skills" / "reportlab" / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    typer.echo(f"wrote {target}")
    typer.echo("for other harnesses, `r2 web skill` prints it to stdout")


def show(project: Project, browser: bool) -> None:
    """Start the daemon if needed, hand the browser a token, say where."""
    from r2.web.daemon import DaemonError, ensure_daemon, reload

    try:
        state = ensure_daemon()
    except DaemonError as exc:
        error(str(exc))
        return
    reload(state)
    query = urlencode({"token": state.token, "to": f"/p/{project.id}"})
    url = f"http://127.0.0.1:{state.port}/auth?{query}"
    typer.echo(f"{project.name}  {url}")
    typer.echo(f"watching {project.reports}")
    if browser:
        webbrowser.open(url)


@web_app.command(hidden=True)
def openapi() -> None:
    """
    Print the OpenAPI schema of the API, which web/ generates its types from.
    """
    _web()
    import json

    from r2.web.app import Viewer

    schema = Viewer([], "", watch=False).app.openapi()
    typer.echo(json.dumps(schema, indent=2, sort_keys=True))
