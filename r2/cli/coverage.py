#
# The `r2 coverage` command group. See dev/spec/coverage.md.
#
import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.markup import escape
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Column

from r2.core import console
from r2.core.coverage import analysis
from r2.core.coverage.analysis import Suite, TestRef, combine, group_by_file
from r2.core.coverage.base import CollectError, Outcome, Span, SpanKind
from r2.core.coverage.workspace import (
    collect as collect_runner,
)
from r2.core.coverage.workspace import (
    detect_runners,
    find_project_root,
    load_maps,
)
from r2.core.messages import error, warn
from r2.core.mode import VERBOSE, mode

app = typer.Typer(
    help="Per-test coverage: which code each test runs.", no_args_is_help=True
)

runner_opt = typer.Option("--runner", help="Only this runner; repeatable.")
baseline_opt = typer.Option(
    "--baseline", help="Selector of the baseline tests; repeatable."
)
span_opt = typer.Option(
    "--span", help="Compare by `native` spans or by `line`.", case_sensitive=False
)

Runners = Annotated[list[str] | None, runner_opt]
Selectors = Annotated[list[str] | None, typer.Argument(help="Test selectors.")]
Baseline = Annotated[list[str] | None, baseline_opt]
SpanMode = Annotated[str, span_opt]


@app.command()
def collect(selectors: Selectors = None, runner: Runners = None) -> None:
    """
    Run the tests under instrumentation and save one map per runner.
    """
    try:
        root = find_project_root(Path.cwd())
    except FileNotFoundError as exc:
        fail(str(exc))
    try:
        runners = detect_runners(root, runner or ())
    except ValueError as exc:
        fail(str(exc))
    error("no test runner detected in the project", not runners)

    missing = [tool for r in runners for tool in r.missing_tools()]
    if missing:
        lines = "\n".join(f"  {tool.name}: {tool.install}" for tool in missing)
        error(f"missing tools:\n{lines}")

    for r in runners:
        if not (mode.summarize or mode.json):
            for suggestion in r.suggestions():
                warn(f"{r.name}: {suggestion}")
        try:
            with Feedback(r.name) as feedback:
                quiet = mode.summarize or mode.json
                result = collect_runner(r, selectors or (), None if quiet else feedback)
        except CollectError as exc:
            tail = "\n".join(exc.output.splitlines()[-30:])
            if tail:
                typer.echo(tail, err=True)
            fail(exc.message)
        failed = sum(1 for t in result.tests.values() if t.outcome == "failed")
        feedback.summary(len(result.tests), failed)


class Feedback:
    """
    Shows the progress of one runner on stderr: a line with the number of
    tests, a transient progress bar and a line for each failed test. The bar
    and the spinner only render on a terminal; colors drop off it.
    """

    def __init__(self, runner: str) -> None:
        self.runner = runner
        self.live: Progress | None = None
        self.task: TaskID | None = None
        self.start = time.monotonic()

    def __enter__(self) -> "Feedback":
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def started(self, total: int) -> None:
        console.stderr.print(
            f"[bold cyan]{self.runner}[/]: running [bold]{total}[/] tests"
        )
        self.live = Progress(
            SpinnerColumn("dots", style="cyan"),
            TextColumn(f"[bold cyan]{self.runner}[/]"),
            BarColumn(
                bar_width=20,
                complete_style="green",
                finished_style="bold green",
                pulse_style="cyan",
            ),
            MofNCompleteColumn(),
            TextColumn(
                "[green]✓ {task.fields[passed]}[/] [red]✗ {task.fields[failed]}[/]"
            ),
            TimeElapsedColumn(),
            # Long test ids end in an ellipsis instead of wrapping the bar.
            TextColumn(
                "[dim]{task.description}[/]",
                table_column=Column(no_wrap=True, overflow="ellipsis", ratio=1),
            ),
            console=console.stderr,
            transient=True,
        )
        self.task = self.live.add_task("", total=total, passed=0, failed=0)
        self._start()

    def finished(self, test: str, outcome: Outcome) -> None:
        if outcome == "failed":
            console.stderr.print(f"  [bold red]✗ FAILED[/] {escape(test)}")
        if self.live is None or self.task is None:
            return
        fields = self.live.tasks[self.task].fields
        counts = {
            "passed": fields["passed"] + (outcome == "passed"),
            "failed": fields["failed"] + (outcome == "failed"),
        }
        self.live.update(self.task, advance=1, description=escape(test), **counts)

    def reading(self) -> None:
        self._stop()
        self.live = Progress(
            SpinnerColumn("dots", style="magenta"),
            TextColumn(f"[bold cyan]{self.runner}[/]: reading coverage data"),
            TimeElapsedColumn(),
            console=console.stderr,
            transient=True,
        )
        self.live.add_task("")
        self._start()

    def summary(self, tests: int, failed: int) -> None:
        """
        The result line on stdout. On a terminal it gains a mark and the time.
        """
        color = "red" if failed else "green"
        line = f"[bold]{self.runner}[/]: {tests} tests, [{color}]{failed} failed[/]"
        if console.stdout.is_terminal:
            mark = "[bold red]✗[/]" if failed else "[bold green]✓[/]"
            line = f"{mark} {line} [dim]in {self.elapsed:.1f}s[/]"
        console.stdout.print(line)

    def _start(self) -> None:
        # Off a terminal rich prints a blank line on stop instead of nothing.
        if self.live is None:
            return
        if console.stderr.is_terminal:
            self.live.start()
        else:
            self.live = None

    def _stop(self) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None


@app.command()
def redundant(
    selectors: Selectors = None,
    baseline: Baseline = None,
    runner: Runners = None,
    span: SpanMode = "native",
) -> None:
    """
    List the tests outside the baseline that add no span.
    """
    base = require_baseline(baseline)
    suite, _ = load_suite(runner, span)
    refs = analysis.redundant(suite, base, selectors or ())
    if mode.json:
        emit_json(
            [ref_data(suite, ref, spans=len(suite.tests[ref].spans)) for ref in refs]
        )
        return
    for ref in refs:
        failed = suite.tests[ref].outcome == "failed"
        out(f"{styled_ref(ref)}{' [red](failed)[/]' if failed else ''}")


@app.command()
def adds(
    selectors: Selectors = None,
    baseline: Baseline = None,
    runner: Runners = None,
    span: SpanMode = "native",
) -> None:
    """
    List the tests outside the baseline that add spans, with the count.
    """
    base = require_baseline(baseline)
    suite, kinds = load_suite(runner, span)
    report_spans(suite, kinds, analysis.adds(suite, base, selectors or ()))


@app.command()
def unique(
    selectors: Selectors = None, runner: Runners = None, span: SpanMode = "native"
) -> None:
    """
    List, for each test, the spans no other test covers.
    """
    suite, kinds = load_suite(runner, span)
    report_spans(suite, kinds, analysis.unique(suite, selectors or ()))


@app.command()
def fragile(
    paths: Annotated[list[str] | None, typer.Argument(help="Only these files.")] = None,
    runner: Runners = None,
    span: SpanMode = "native",
) -> None:
    """
    List the spans covered by exactly one test.
    """
    suite, kinds = load_suite(runner, span)
    found = analysis.fragile(suite, paths or ())
    if mode.json:
        emit_json(
            [
                {"span": str(sp), "test": ref.id, "runner": ref.runner}
                for sp, ref in found
            ]
        )
        return
    grouped: dict[tuple[str, TestRef], set[Span]] = {}
    for sp, ref in found:
        grouped.setdefault((sp.path, ref), set()).add(sp)
    rows = []
    for (path, ref), spans in grouped.items():
        ranges = group_by_file(frozenset(spans), kinds[ref.runner]).get(path, [])
        if ranges:
            rows.append((path, ranges[0][0], ref, ranges))
    for path, _, ref, ranges in sorted(rows, key=lambda r: r[:3]):
        out(f"{styled_path(path)}:{styled_ranges(ranges)}  {styled_ref(ref)}")


@app.command()
def minimize(
    selectors: Selectors = None,
    baseline: Baseline = None,
    runner: Runners = None,
    span: SpanMode = "native",
) -> None:
    """
    Print a small set of tests that keeps the whole coverage.
    """
    suite, _ = load_suite(runner, span)
    result = analysis.minimize(suite, baseline or (), selectors or ())
    if mode.json:
        emit_json(
            {
                "kept": [ref.id for ref in result.kept],
                "dropped": [ref.id for ref in result.dropped],
            }
        )
        return
    for ref in result.kept:
        out(styled_ref(ref))
    total = len(result.kept) + len(result.dropped)
    out(f"[bold]kept [green]{len(result.kept)}[/] of {total} tests[/]")


@app.command()
def show(
    test: Annotated[str, typer.Argument(help="Test id.")],
    baseline: Baseline = None,
    runner: Runners = None,
    span: SpanMode = "native",
) -> None:
    """
    Print the spans of one test, and the ones it adds over the baseline.
    """
    suite, kinds = load_suite(runner, span)
    found = sorted(ref for ref in suite.tests if ref.id == test)
    error(f"no test with id {test!r} in the coverage maps", not found)
    ref = found[0]
    record = suite.tests[ref]
    extra = analysis.added(suite, ref, baseline) if baseline else None
    if mode.json:
        emit_json(
            {
                "test": ref.id,
                "runner": ref.runner,
                "outcome": record.outcome,
                "spans": sorted(str(sp) for sp in record.spans),
                "adds": None if extra is None else sorted(str(sp) for sp in extra),
            }
        )
        return
    kind = kinds[ref.runner]
    for path, ranges in group_by_file(record.spans, kind).items():
        out(f"[dim]covers[/] {styled_path(path)}: {styled_ranges(ranges)}")
    if extra:
        for path, ranges in group_by_file(extra, kind).items():
            out(f"[bold green]adds[/] {styled_path(path)}: {styled_ranges(ranges)}")


#
# HELPERS
#
def fail(message: str) -> NoReturn:
    """
    Print an error and exit with status 1.
    """
    error(message)
    raise typer.Exit(1)


def require_baseline(baseline: list[str] | None) -> list[str]:
    if not baseline:
        raise typer.BadParameter("give at least one test.", param_hint="--baseline")
    return baseline


def load_suite(names: list[str] | None, span: str) -> tuple[Suite, dict[str, SpanKind]]:
    """
    The suite of the saved maps and the span kind its spans have per runner.
    Warns about stale maps. Exits with an error when there is no map.
    """
    kind = span.lower()
    if kind not in ("native", "line"):
        raise typer.BadParameter("use `native` or `line`.", param_hint="--span")
    try:
        root = find_project_root(Path.cwd())
        maps = load_maps(root, names or ())
    except FileNotFoundError as exc:
        fail(f"{exc}; run `r2 coverage collect`")
    for cmap in maps:
        stale = cmap.stale_files(root)
        warn(f"{cmap.runner} map is stale: {', '.join(stale)}", bool(stale))
    by_line = kind == "line"
    suite = combine(maps, by_line=by_line)
    kinds: dict[str, SpanKind] = {
        cmap.runner: "line" if by_line else cmap.span_kind for cmap in maps
    }
    return suite, kinds


def report_spans(
    suite: Suite,
    kinds: dict[str, SpanKind],
    rows: Sequence[tuple[TestRef, frozenset[Span]]],
) -> None:
    """
    Print tests with their span counts; at -v also the spans by file.
    """
    if mode.json:
        emit_json(
            [
                ref_data(suite, ref, spans=sorted(str(sp) for sp in spans))
                for ref, spans in rows
            ]
        )
        return
    for ref, spans in rows:
        count = len(spans)
        noun = "span" if count == 1 else "spans"
        out(f"{styled_ref(ref)}: [bold yellow]{count}[/] {noun}")
        if mode.verbosity >= VERBOSE:
            for path, ranges in group_by_file(spans, kinds[ref.runner]).items():
                out(f"  {styled_path(path)}: {styled_ranges(ranges)}")


def ref_data(suite: Suite, ref: TestRef, **extra: Any) -> dict[str, Any]:
    return {
        "test": ref.id,
        "runner": ref.runner,
        "outcome": suite.tests[ref].outcome,
        **extra,
    }


def format_ranges(ranges: Sequence[tuple[int, int]]) -> str:
    return ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)


def out(markup: str) -> None:
    """
    Print a result line on stdout. Colors only show on a terminal; piped and
    agent output get the same text without them.
    """
    console.stdout.print(markup)


def styled_ref(ref: TestRef) -> str:
    """
    The test id with its file part dim and the test name bold.
    """
    for sep in ("::", " > "):
        head, found, name = ref.id.rpartition(sep)
        if found:
            return f"[dim]{escape(head + sep)}[/][bold]{escape(name)}[/]"
    return f"[bold]{escape(ref.id)}[/]"


def styled_path(path: str) -> str:
    return f"[blue]{escape(path)}[/]"


def styled_ranges(ranges: Sequence[tuple[int, int]]) -> str:
    return f"[cyan]{format_ranges(ranges)}[/]"


def emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
