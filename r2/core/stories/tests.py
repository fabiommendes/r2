"""
The end-to-end tests of a project and the story each one cites.

Tests are found by reading the test files, without running any test runner:

- vitest and playwright: the title of `test(...)` or `it(...)` is the story
  id, as in `test("student: log in", ...)`;
- pytest: a test function cites a story with `@pytest.mark.story("student:
  log in")`, on the function or on its class.

Every test found in the e2e paths is an e2e test, so a test that cites no
story is reported by the checks.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from r2.core.stories.doc import parse_id

__all__ = ["StoryTest", "find_tests", "python_tests", "script_tests"]

SKIPPED_DIRS = {"node_modules", "__pycache__", "venv"}
SCRIPT_RE = re.compile(r".*\.(test|spec)\.[cm]?[jt]sx?")
SCRIPT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
PYTHON_RE = re.compile(r"(test_.*|.*_test)\.py")

# test("title", ...), it('title', ...), test.only(`title`, ...); not
# test.describe, test.step or test.beforeEach.
TEST_CALL_RE = re.compile(
    r"""(?<![\w$.])(?:test|it)(?:\.(?:only|skip|fixme|fail|concurrent))*\(\s*"""
    r"""(?P<quote>["'`])(?P<title>(?:\\.|(?!(?P=quote))[^\\\n])*)(?P=quote)"""
)
ESCAPE_RE = re.compile(r"\\(.)")


@dataclass(frozen=True, order=True)
class StoryTest:
    """One e2e test, or one story citation of a test that cites several."""

    path: str
    """The test file, relative to the project root."""
    line: int
    name: str
    """The test title (vitest, playwright) or its pytest node id."""
    cites: str | None
    """The story the test cites, as written; None when it cites none."""

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}"

    @property
    def story(self) -> str | None:
        """The id of the cited story, `role: slug`, or None."""
        parsed = parse_id(self.cites) if self.cites is not None else None
        return f"{parsed[0]}: {parsed[1]}" if parsed else None


def find_tests(root: Path, paths: Iterable[Path]) -> list[StoryTest]:
    """
    The e2e tests in paths, files or folders, sorted by file and line. A
    path that does not exist is skipped.
    """
    found: set[StoryTest] = set()
    for file in _files(paths):
        rel = _relative(file, root)
        text = file.read_text(encoding="utf-8", errors="replace")
        if file.suffix == ".py":
            found.update(python_tests(text, rel))
        else:
            found.update(script_tests(text, rel))
    return sorted(found)


def script_tests(text: str, path: str) -> list[StoryTest]:
    """
    The tests of a vitest or playwright file. A title of the form
    `role: title` cites that story; any other title cites none.
    """
    tests: list[StoryTest] = []
    for match in TEST_CALL_RE.finditer(text):
        title = ESCAPE_RE.sub(r"\1", match.group("title"))
        line = text.count("\n", 0, match.start()) + 1
        cites = title if parse_id(title) else None
        tests.append(StoryTest(path, line, title, cites))
    return tests


def python_tests(text: str, path: str) -> list[StoryTest]:
    """
    The test functions of a pytest file, one entry per story marker. A test
    without a marker gives one entry that cites no story.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    tests: list[StoryTest] = []
    for node, prefix, inherited in _test_functions(tree.body, path, []):
        name = f"{prefix}::{node.name}"
        cites = inherited + _markers(node.decorator_list)
        tests += [StoryTest(path, node.lineno, name, story) for story in cites]
        if not cites:
            tests.append(StoryTest(path, node.lineno, name, None))
    return tests


type _Function = ast.FunctionDef | ast.AsyncFunctionDef


def _test_functions(
    body: list[ast.stmt], prefix: str, inherited: list[str]
) -> Iterator[tuple[_Function, str, list[str]]]:
    """The test functions in body, with their node id prefix and class markers."""
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test"):
                yield node, prefix, inherited
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from _test_functions(
                node.body,
                f"{prefix}::{node.name}",
                inherited + _markers(node.decorator_list),
            )


def _markers(decorators: list[ast.expr]) -> list[str]:
    """The stories of the `story` markers among decorators."""
    stories: list[str] = []
    for decorator in decorators:
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "story"
            and _is_mark(decorator.func.value)
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
        ):
            stories.append(decorator.args[0].value)
    return stories


def _is_mark(node: ast.expr) -> bool:
    """Whether node is `pytest.mark` or a bare `mark`."""
    if isinstance(node, ast.Name):
        return node.id == "mark"
    return isinstance(node, ast.Attribute) and node.attr == "mark"


def _files(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_file():
            if path.suffix == ".py" or path.suffix in SCRIPT_SUFFIXES:
                yield path
        elif path.is_dir():
            for file in sorted(path.rglob("*")):
                if _is_test_file(file, path):
                    yield file


def _is_test_file(file: Path, top: Path) -> bool:
    parts = file.relative_to(top).parts[:-1]
    if any(part in SKIPPED_DIRS or part.startswith(".") for part in parts):
        return False
    return file.is_file() and (
        PYTHON_RE.fullmatch(file.name) is not None
        or SCRIPT_RE.fullmatch(file.name) is not None
    )


def _relative(file: Path, root: Path) -> str:
    try:
        return file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return file.as_posix()
