"""
Tests for the user story format, the e2e test discovery and the checks
(dev/spec/stories.md).
"""

from __future__ import annotations

from pathlib import Path

from r2.core.stories import check as checks
from r2.core.stories.doc import parse, parse_id, slugify, story_id
from r2.core.stories.tests import find_tests, python_tests, script_tests

STRICT = """\
---
type: stories
status: active
role: student
---

# Student user stories

Students read the material.

## Joining the platform

### Log in

    status: implemented
    url: /login
    relatedTo: [login-bug]

Student opens the login page.

### Reset the password

Student forgot it.

## Exams

### Take an exam

    status: web
    owner: ana

Student answers the questions.
"""


def test_slug_and_id() -> None:
    assert slugify("Import a term's calendar") == "import-a-term-s-calendar"
    assert slugify("Configuração do curso") == "configuracao-do-curso"
    assert story_id("admin", "Read the API documentation") == (
        "admin: read-the-api-documentation"
    )
    assert parse_id("admin: read the api documentation") == (
        "admin",
        "read-the-api-documentation",
    )
    assert parse_id("admin:read-the-api-documentation") == parse_id(
        "admin: Read the API documentation"
    )
    assert parse_id("no role here") is None
    assert parse_id("admin: !!!") is None


def test_parse_strict_file() -> None:
    doc = parse(STRICT, "ignored")
    assert doc.role == "student"
    assert doc.title == "Student user stories"
    assert doc.intro == "Students read the material."
    assert [s.name for s in doc.sections] == ["Joining the platform", "Exams"]
    login, reset, exam = doc.stories
    assert login.meta == {
        "status": "implemented",
        "url": "/login",
        "relatedTo": ["login-bug"],
    }
    assert login.narrative == "Student opens the login page."
    assert reset.status == "todo"
    assert reset.meta == {}
    assert reset.narrative == "Student forgot it."
    assert exam.status == "web"
    assert exam.needs_test
    assert not reset.needs_test


def test_strict_file_round_trips() -> None:
    assert parse(STRICT, "student").to_markdown() == STRICT.replace(
        "### Reset the password\n\n", "### Reset the password\n\n    status: todo\n\n"
    )


def test_lenient_reading() -> None:
    text = """\
### Before any section

    not: [valid yaml

Narrative.

```md
### Not a story
```

## Section

    plain indented code

#### Deeper heading
"""
    doc = parse(text, "guest")
    assert doc.role == "guest"
    assert doc.title == "Guest user stories"
    first = doc.sections[0]
    assert first.name == ""
    (story,) = first.stories
    assert story.meta == {}
    assert story.narrative.startswith("    not: [valid yaml")
    assert "### Not a story" in story.narrative
    assert doc.sections[1].intro.startswith("    plain indented code")
    again = parse(doc.to_markdown(), "x")
    assert [s.title for s in again.stories] == ["Before any section"]


def test_script_tests() -> None:
    text = """\
test.beforeEach(reset);
test("admin: check that the instance is healthy", async () => {
  await test.step("admin: not a test", async () => {});
});
test.only('student: log in', () => {});
it(`renders the page`, () => {});
test.describe("admin: a group", () => {});
"""
    tests = script_tests(text, "a.test.ts")
    assert [(t.line, t.story) for t in tests] == [
        (2, "admin: check-that-the-instance-is-healthy"),
        (5, "student: log-in"),
        (6, None),
    ]


def test_python_tests() -> None:
    text = """\
import pytest
from pytest import mark


@pytest.mark.story("student: log in")
def test_login(): ...


@mark.story("student: log in")
@mark.story("student: reset the password")
def test_two(): ...


def test_none(): ...


@pytest.mark.story("student: take an exam")
class TestExam:
    def test_answer(self): ...

    def helper(self): ...
"""
    tests = python_tests(text, "tests/stories/test_x.py")
    assert [(t.name.split("::", 1)[1], t.story) for t in tests] == [
        ("test_login", "student: log-in"),
        ("test_two", "student: log-in"),
        ("test_two", "student: reset-the-password"),
        ("test_none", None),
        ("TestExam::test_answer", "student: take-an-exam"),
    ]


def test_find_tests_skips_other_files(tmp_path: Path) -> None:
    folder = tmp_path / "e2e"
    (folder / "node_modules" / "x").mkdir(parents=True)
    (folder / "node_modules" / "x" / "a.test.ts").write_text('test("a: b", f)')
    (folder / "helpers.ts").write_text('test("a: b", f)')
    (folder / "login.spec.ts").write_text('test("a: b", f)')
    (folder / "test_a.py").write_text("def test_a(): ...")
    found = find_tests(tmp_path, [folder, tmp_path / "missing"])
    assert [t.location for t in found] == ["e2e/login.spec.ts:1", "e2e/test_a.py:1"]


def write_stories(root: Path, text: str = STRICT, name: str = "student") -> Path:
    path = root / "docs" / "user-stories" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def write_test(root: Path, text: str, name: str = "student.test.ts") -> Path:
    path = root / "test" / "stories" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def run_check(root: Path, no_duplicates: bool = False) -> checks.Report:
    return checks.run(checks.layout(root), no_duplicates)


def messages(problems: list[checks.Problem]) -> list[str]:
    return [str(problem) for problem in problems]


def test_check_reports_both_directions(tmp_path: Path) -> None:
    write_stories(tmp_path)
    write_test(
        tmp_path,
        """\
test("student: log in", f);
test("student: reset the password", f);
test("student: sign up", f);
test("no story here", f);
""",
    )
    report = run_check(tmp_path)
    assert messages(report.errors) == [
        "test/stories/student.test.ts:3: 'student: sign up' cites no existing story",
        "test/stories/student.test.ts:4: 'no story here' cites no story",
        "student: take-an-exam: has no test (status: web)",
    ]
    assert messages(report.warnings) == [
        "test/stories/student.test.ts:2: tests a todo story"
    ]
    assert [ref.id for ref in report.missing()] == ["student: take-an-exam"]
    assert [t.line for t in report.stale()] == [3, 4]
    assert report.coverage() == [
        {"role": "student", "stories": 3, "tested": 2, "need_test": 2}
    ]


def test_check_duplicates(tmp_path: Path) -> None:
    write_stories(tmp_path, STRICT + "\n### Log-in\n\nAgain.\n")
    write_test(
        tmp_path,
        'test("student: log in", f);\ntest("student: Log in", f);\n'
        'test("student: take an exam", f);\n',
    )
    assert messages(run_check(tmp_path).errors) == [
        "docs/user-stories/student.md: 'Log-in' and 'Log in' share the id "
        "student: log-in",
    ]
    assert messages(run_check(tmp_path, no_duplicates=True).errors)[1:] == [
        "student: log-in: has 2 tests: test/stories/student.test.ts:1, "
        "test/stories/student.test.ts:2"
    ]


def test_check_duplicate_role(tmp_path: Path) -> None:
    write_stories(tmp_path)
    write_stories(tmp_path, "---\ntype: stories\nrole: student\n---\n", "zz")
    assert messages(run_check(tmp_path).errors)[0] == (
        "docs/user-stories/zz.md: role 'student' is also docs/user-stories/student.md"
    )


def test_layout_reads_project_config(tmp_path: Path) -> None:
    (tmp_path / "r2.toml").write_text(
        '[config.stories]\ndir = "stories"\ntests = ["e2e", "more"]\n'
    )
    where = checks.layout(tmp_path)
    assert where.stories == tmp_path / "stories"
    assert where.tests == [tmp_path / "e2e", tmp_path / "more"]
    given = checks.layout(tmp_path, tmp_path / "x", [tmp_path / "y"])
    assert (given.stories, given.tests) == (tmp_path / "x", [tmp_path / "y"])


def test_layout_defaults(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "tests" / "stories").mkdir(parents=True)
    sub = tmp_path / "src"
    sub.mkdir()
    where = checks.layout(sub)
    assert where.root == tmp_path
    assert where.stories == tmp_path / "docs" / "user-stories"
    assert where.tests == [tmp_path / "tests" / "stories"]


def test_readme_and_coverage_are_not_story_files(tmp_path: Path) -> None:
    write_stories(tmp_path)
    write_stories(tmp_path, "# User stories\n\n### Not a story\n", "README")
    write_stories(tmp_path, "# Story coverage\n", "coverage")
    assert [p.name for p in checks.story_paths(tmp_path / "docs" / "user-stories")] == [
        "student.md"
    ]
