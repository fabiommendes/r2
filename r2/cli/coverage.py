#
# The `r2 coverage` command group. See dev/spec/coverage.md.
#
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from r2.core.coverage import analysis
from r2.core.coverage.analysis import Suite, TestRef, combine, group_by_file
from r2.core.coverage.base import CollectError, Span, SpanKind
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

app = typer.Typer(help="Per-test coverage: which code each test runs.")

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
        try:
            result = collect_runner(r, selectors or ())
        except CollectError as exc:
            tail = "\n".join(exc.output.splitlines()[-30:])
            if tail:
                typer.echo(tail, err=True)
            fail(exc.message)
        failed = sum(1 for t in result.tests.values() if t.outcome == "failed")
        typer.echo(f"{r.name}: {len(result.tests)} tests, {failed} failed")


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
        typer.echo(f"{ref}{' (failed)' if failed else ''}")


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
        typer.echo(f"{path}:{format_ranges(ranges)}  {ref}")


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
        typer.echo(str(ref))
    total = len(result.kept) + len(result.dropped)
    typer.echo(f"kept {len(result.kept)} of {total} tests")


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
        typer.echo(f"covers {path}: {format_ranges(ranges)}")
    if extra:
        for path, ranges in group_by_file(extra, kind).items():
            typer.echo(f"adds {path}: {format_ranges(ranges)}")


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
        typer.echo(f"{ref}: {count} span{'' if count == 1 else 's'}")
        if mode.verbosity >= VERBOSE:
            for path, ranges in group_by_file(spans, kinds[ref.runner]).items():
                typer.echo(f"  {path}: {format_ranges(ranges)}")


def ref_data(suite: Suite, ref: TestRef, **extra: Any) -> dict[str, Any]:
    return {
        "test": ref.id,
        "runner": ref.runner,
        "outcome": suite.tests[ref].outcome,
        **extra,
    }


def format_ranges(ranges: Sequence[tuple[int, int]]) -> str:
    return ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)


def emit_json(data: Any) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
