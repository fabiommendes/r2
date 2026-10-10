---
type: spec
status: draft
tags: [coverage, tests, redundancy, python, rust, typescript]
relatedTo: [cli]
---

# Per-test coverage

`r2 coverage` records which code each test runs and answers questions about
the test suite from that record: which tests add nothing over a core suite,
which code only one test reaches, the smallest set of tests that keeps the
coverage. The target use is pruning the many shallow tests that coding
agents tend to write. A redundant test is a candidate for review, never an
automatic deletion: a test can add no coverage and still be the only one
that checks a result.

Mutation testing, which confirms or rejects a candidate, is out of scope
here and gets its own spec on top of the same test ids and selectors.

The examples in `tests/examples/roman/` are the acceptance baseline: the
catalog in their README is the expected output of the analysis commands.

## Concepts

1. A **runner** is a test tool r2 knows how to instrument. One project can
   have several (vitest and playwright in the same `package.json`).

   | Runner | Language | Mechanism | Unit |
   | --- | --- | --- | --- |
   | `pytest` | Python | coverage.py dynamic contexts, one run | arc |
   | `nextest` | Rust | one `.profraw` per test, `llvm-cov export` | region |
   | `vitest` | TS | V8 coverage taken per test in a setup file | block |
   | `playwright` | TS | page V8 coverage per test in a fixture | block |

2. A **unit** is the smallest piece of code the runner tells apart. Every
   unit belongs to a source file and a line range, so any unit can be
   reduced to the lines it spans.
3. A **test id** is the runner's own id: the pytest node id
   (`tests/test_examples.py::test_from_roman_iv`), the nextest id
   (`roman::examples to_roman_rejects_zero`), and `file > title` for vitest
   and playwright. Parametrized cases are separate tests.
4. The **baseline** is the set of units that run outside any test: imports,
   module level code, session fixtures. Every analysis treats the baseline
   as covered by everyone, so importing a module never counts as coverage
   a test adds.
5. A **selector** picks tests by id. It is a glob (`*properties*`) matched
   against the full id; `runner:glob` restricts it to one runner
   (`vitest:*properties*`). Several selectors combine with "or".
6. The **core** is the set of tests picked by the `--core` selectors. Only
   the analyses that compare against something need it.
7. A test **adds** a unit when it covers the unit and neither the core nor
   the baseline does.

## Coverage map

8. `r2 coverage collect` writes one coverage map per runner to
   `.r2/coverage/<runner>.json` at the project root, the folder of the
   detected project. The first write also creates `.r2/.gitignore`
   holding `*`.
9. A map holds:
   - `runner`, `unit` (`arc`, `region`, `block` or `line`), r2's format
     `version`;
   - `created`, the git commit and whether the tree was dirty;
   - `files`: each measured source file with the hash of its content;
   - `baseline`: the baseline units;
   - `tests`: for each test id, its outcome (`passed`, `failed`,
     `skipped`) and its units.

   Units are written as `path:line:col-line:col`, with paths relative to
   the project root.
10. A map is **stale** when a measured file changed since it was written.
    The analysis commands still run on a stale map and print a warning
    with the changed files.
11. A failing test is still recorded, with outcome `failed`. Analyses
    include it and mark it in the output. A skipped test has no units.

## Commands

All commands take `-C` and the global options from [cli.md](cli.md).

### collect

12. `r2 coverage collect [--runner NAME]... [SELECTOR]...` runs the tests
    under instrumentation and writes the maps. Without `--runner`, it runs
    every runner it detects; without selectors, every test.
13. Detection reads the project files r2.core.project already parses:
    - `pytest` in the dependencies of a uv project;
    - a `Cargo.toml` (nextest is a tool, not a dependency);
    - `vitest` or `@playwright/test` in the `package.json` dependencies.
14. Before running, `collect` checks the external tools each runner needs
    and, if any is missing, fails with exit 1 listing each one with its
    install command. It never installs anything.

    | Runner | Needs |
    | --- | --- |
    | `pytest` | `uv`; `pytest-cov` or `coverage` in the project, else run through `uv run --with coverage` |
    | `nextest` | `cargo`, `cargo-nextest`, `llvm-tools-preview` (`llvm-profdata`, `llvm-cov`) |
    | `vitest` | `npx`, `vitest` in `node_modules` |
    | `playwright` | `npx`, `@playwright/test` in `node_modules`, a Chromium browser |

15. `collect` never changes the project's files. Instrumentation goes
    through environment variables, command line flags and files under
    `.r2/coverage/`, such as the vitest setup file r2 passes with
    `--setupFiles`.
16. A test failure does not fail `collect`: it exits 0 when it wrote the
    map, and prints one line per runner, `pytest: 12 tests, 1 failed`.
    It exits 1 when a runner could not run at all (build error, no tests
    collected), and shows the runner's last 30 lines of output.
17. Collecting with selectors replaces the recorded tests that match them
    and keeps the others, so one test can be refreshed without running
    the whole suite. The baseline is replaced on every run.

### Analyses

18. The analysis commands read the maps and never run tests. They read
    every map unless `--runner` is given. A missing map is an error that
    points to `r2 coverage collect`.
19. When maps with different units are read together (vitest blocks and
    playwright blocks are the same unit; pytest arcs and vitest blocks are
    not, but they never share files), each file is compared at the
    coarsest unit any map uses for it, down to `line`. `--unit line`
    forces lines everywhere.

20. `r2 coverage redundant --core SELECTOR... [SELECTOR]...` lists the
    tests outside the core that add no unit. With selectors, only those
    tests are checked. Each line is the test id. With `--json`: a list of
    `{"test", "runner", "outcome", "units"}`, where `units` is the count
    of units the test covers.
21. `r2 coverage adds --core SELECTOR... [SELECTOR]...` is the opposite:
    each test outside the core that adds units, with the count, sorted by
    the count, largest first. `-v` also lists the units, grouped by file
    as line ranges.
22. `r2 coverage unique [SELECTOR]...` lists, for each test, the units no
    other test covers, as `test: N units`. Tests with none are left out.
    `-v` lists the units.
23. `r2 coverage fragile [PATH]...` lists the units covered by exactly one
    test, grouped by file, with the test. With paths, only those files.
24. `r2 coverage minimize [--core SELECTOR]... [SELECTOR]...` prints a
    small set of tests that covers every unit the whole suite covers,
    found with the greedy set cover: the core first, then at each step the
    test that adds the most units. Ties go to the test with fewer units,
    then to the id. The last line reads `kept 8 of 12 tests`. With
    `--json`: `{"kept": [...], "dropped": [...]}`.
25. `r2 coverage show TEST` prints the units of one test, grouped by file
    as line ranges, marking the ones the test adds when `--core` is given.

### Later

Not part of this spec, but the map is designed for them:

- `overlap`: a matrix of shared units between test files.
- `impact DIFF`: the tests that cover the lines a diff touches.

## Code

26. `r2.core.coverage` is a package:

    | Module | Holds |
    | --- | --- |
    | `base.py` | `CoverageMap`, `Unit`, `TestId`, `CoverageRunner` |
    | `analysis.py` | the analyses as pure functions on maps |
    | `py.py` | `PytestCoverage` |
    | `rs.py` | `NextestCoverage` |
    | `ts.py` | `VitestCoverage`, `PlaywrightCoverage` |

27. `CoverageRunner` is an abstract class. A runner holds the project it
    works on (`UvProject`, `CargoProject`, `NpmProject`) and implements:

    ```python
    class CoverageRunner(ABC):
        name: ClassVar[str]
        unit: ClassVar[UnitKind]
        project: Project

        @classmethod
        def detect(cls, project: Project) -> bool: ...
        def missing_tools(self) -> list[MissingTool]: ...  # name + install hint
        def collect(self, selectors: list[str]) -> CoverageMap: ...
    ```

28. The analyses import nothing from the runners and run no programs, so
    they are tested on hand built maps without any toolchain.
29. Runners call programs through `r2.core.cli_tool.CliTool`, which needs:
    - a call that returns the exit code, stdout and stderr without
      raising, since a runner exits non-zero when a test fails;
    - `_env` merged over the current environment instead of replacing it;
    - `available()` and an install hint, for `missing_tools`.
30. `r2.core.project` gains `CargoProject` and `NpmProject`, with only what
    coverage needs: detection, root, dependencies. Their other `Project`
    methods raise `NotImplementedError`. `find_projects(path)` returns
    every project at a path, since one folder can hold a `pyproject.toml`
    and a `package.json`.

## Acceptance

Run against copies of `tests/examples/roman/`:

31. For each of `python/`, `rust/` and `ts/`, `collect` writes a map with
    all the tests of the catalog, the 2 property tests included.
32. `redundant --core '*properties*'` prints exactly the tests the catalog
    marks "redundant" for that language; `adds` prints the others. In
    `ts/`, the playwright tests are redundant on `src/roman.ts` but add
    units in `src/main.ts`, so they show up in `adds`.
33. `minimize --core '*properties*'` keeps the core and drops every test
    `redundant` lists, plus one of `to_roman_rejects_zero` and
    `to_roman_rejects_4000`.
34. Running `collect` twice on an unchanged project gives the same tests
    and units.
35. With a tool missing (for example `cargo-nextest` off the `PATH`),
    `collect` exits 1 and names the tool and its install command.

## Open points

- Where the core lives besides the command line: a `[coverage] core`
  entry in r2's per-project config would save typing `--core` on every
  call.
- The vitest and playwright mechanisms are the least proven. A spike
  confirms them before the TS runners are implemented.
