"""
Tests for `r2 story` (dev/spec/stories.md), in-process through the root app.

The acceptance tests run against a copy of tests/examples/stories/codehood,
a slice of the codehood stories and playwright tests.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import app
from r2.core.stories.doc import parse
from tests.support import REPO_ROOT

runner = CliRunner()

CODEHOOD = REPO_ROOT / "tests" / "examples" / "stories" / "codehood"

UNTESTED = [
    "admin: create-the-first-admin: has no test (status: cli)",
    "admin: reset-a-password-for-someone-locked-out: has no test (status: cli)",
    "admin: import-a-term-s-calendar-for-an-instructor: has no test (status: cli)",
]


@pytest.fixture(autouse=True)
def _human_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("R2_AGENT", raising=False)


@pytest.fixture
def codehood(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "codehood"
    shutil.copytree(CODEHOOD, root)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "docs" / "user-stories").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def r2(*args: str, input: str | None = None) -> tuple[int, str]:
    result = runner.invoke(app, list(args), input=input)
    return result.exit_code, result.output


def lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line]


#
# ACCEPTANCE: THE CODEHOOD SLICE
#
def test_check_codehood(codehood: Path) -> None:
    code, output = r2("story", "check")
    assert code == 1
    assert lines(output) == [
        *UNTESTED,
        "admin: 9 of 16 stories have a test (12 implemented or partial)",
    ]


def test_check_modes_codehood(codehood: Path) -> None:
    code, output = r2("story", "check", "--missing")
    assert code == 0
    assert [line.split("  ")[1] for line in lines(output)] == [
        "cli",
        "todo",
        "cli",
        "todo",
        "cli",
        "todo",
        "todo",
    ]
    code, output = r2("story", "check", "--covered")
    assert code == 0
    assert len(lines(output)) == 9
    assert lines(output)[0] == (
        "admin: check-that-the-instance-is-healthy  implemented  "
        "Check that the instance is healthy"
    )
    assert r2("story", "check", "--stale") == (0, "")
    code, output = r2("story", "check", "--no-duplicates")
    assert (code, lines(output)[:-1]) == (1, UNTESTED)


def test_check_reports_a_renamed_story(codehood: Path) -> None:
    r2("story", "fmt")
    code, _ = r2("story", "set", "admin: create a discipline", "--title", "Add one")
    assert code == 0
    code, output = r2("story", "check")
    assert code == 1
    assert (
        "test/stories/admin-disciplines-and-editions.test.ts:16: "
        "'admin: create a discipline' cites no existing story"
    ) in lines(output)
    assert "admin: add-one: has no test (status: implemented)" in lines(output)
    code, output = r2("story", "check", "--stale")
    assert lines(output) == [
        "test/stories/admin-disciplines-and-editions.test.ts:16  "
        "admin: create a discipline"
    ]


def test_check_json(codehood: Path) -> None:
    code, output = r2("--json", "story", "check")
    data = json.loads(output)
    assert code == 1
    assert [e["subject"] for e in data["errors"]] == [
        line.split(": has")[0] for line in UNTESTED
    ]
    assert data["errors"][0]["kind"] == "untested"
    assert data["coverage"] == [
        {"role": "admin", "stories": 16, "tested": 9, "need_test": 12}
    ]
    _, output = r2("--json", "story", "check", "--covered")
    assert json.loads(output)[0]["tests"] == [
        "test/stories/admin-bootstrapping-the-instance.test.ts:6"
    ]


def test_list_and_show_codehood(codehood: Path) -> None:
    code, output = r2("story", "list", "--status", "cli")
    assert code == 0
    assert lines(output) == [
        "admin: create-the-first-admin  cli  Create the first admin",
        "admin: reset-a-password-for-someone-locked-out  cli  "
        "Reset a password for someone locked out",
        "admin: import-a-term-s-calendar-for-an-instructor  cli  "
        "Import a term's calendar for an instructor",
    ]
    code, output = r2("story", "show", "admin: check that the instance is healthy")
    assert code == 0
    assert output.startswith(
        "### Check that the instance is healthy\n\n"
        "    status: implemented\n    url: /api/health\n\nSysadmin"
    )
    _, output = r2("--json", "story", "show", "admin:read-the-api-documentation")
    data = json.loads(output)
    assert data["section"] == "Bootstrapping the instance"
    assert data["meta"] == {"status": "implemented", "url": "/api/docs"}
    assert r2("story", "show", "admin: nothing")[0] == 1
    assert r2("story", "show", "no role")[0] == 2


def test_fmt_keeps_the_stories(codehood: Path) -> None:
    _, before = r2("story", "list")
    code, _ = r2("story", "fmt")
    assert code == 0
    path = codehood / "docs" / "user-stories" / "admin.md"
    assert path.read_text().startswith("---\ntype: stories\nstatus: active\n")
    assert r2("story", "list") == (0, before)
    readme = codehood / "docs" / "user-stories" / "README.md"
    assert readme.read_text() == (CODEHOOD / "docs/user-stories/README.md").read_text()


def test_writes_refuse_a_lenient_file(codehood: Path) -> None:
    code, output = r2("story", "remove", "admin: create the first admin")
    assert code == 1
    assert "r2 story fmt" in output


#
# WRITING
#
def test_new_set_remove(empty: Path) -> None:
    code, _ = r2(
        "story",
        "new",
        "student: Log in",
        "--section",
        "Joining",
        "--status",
        "implemented",
        "--url",
        "/login",
        "--relatedTo",
        "a, b",
        "--body",
        "-",
        input="Student logs in.\n",
    )
    assert code == 0
    path = empty / "docs" / "user-stories" / "student.md"
    assert path.read_text() == (
        "---\ntype: stories\nstatus: active\nrole: student\n---\n\n"
        "# Student user stories\n\n## Joining\n\n### Log in\n\n"
        "    status: implemented\n    url: /login\n    relatedTo: [a, b]\n\n"
        "Student logs in.\n"
    )
    assert r2("story", "new", "student: Log-in")[0] == 1
    assert r2("story", "new", "student: Sign up")[0] == 0
    assert parse(path.read_text(), "x").sections[0].stories[1].title == "Sign up"

    code, _ = r2(
        "story", "set", "student: log in", "--status", "partial", "--unset", "url"
    )
    assert code == 0
    code, _ = r2("story", "set", "student: sign up", "--section", "Accounts")
    assert code == 0
    doc = parse(path.read_text(), "x")
    login = doc.find("log-in")
    assert login is not None
    assert login.meta == {"status": "partial", "relatedTo": ["a", "b"]}
    assert [s.name for s in doc.sections] == ["Joining", "Accounts"]
    assert r2("story", "set", "student: log in", "--title", "Sign up")[0] == 1

    assert r2("story", "remove", "student: sign up")[0] == 0
    assert [s.title for s in parse(path.read_text(), "x").stories] == ["Log in"]
    assert r2("story", "remove", "student: sign up")[0] == 1


def test_write_usage_errors(empty: Path) -> None:
    assert r2("story", "new", "Log in")[0] == 2
    assert r2("story", "new", "student: Log in", "--status", "web")[0] == 2
    r2("story", "new", "student: Log in")
    assert r2("story", "set", "student: log in")[0] == 2


def test_pytest_markers(empty: Path) -> None:
    r2("story", "new", "student: Log in", "--status", "implemented")
    tests = empty / "tests" / "stories"
    tests.mkdir(parents=True)
    (tests / "test_login.py").write_text(
        "import pytest\n\n\n"
        '@pytest.mark.story("student: log in")\n'
        "def test_login(): ...\n\n\n"
        "def test_other(): ...\n"
    )
    code, output = r2("story", "check")
    assert code == 1
    assert lines(output) == [
        "tests/stories/test_login.py:8: "
        "'tests/stories/test_login.py::test_other' cites no story",
        "student: 1 of 1 stories have a test (1 implemented or partial)",
    ]


def test_check_without_test_folder(empty: Path) -> None:
    r2("story", "new", "student: Log in")
    result = runner.invoke(app, ["story", "check"])
    assert result.exit_code == 0
    assert "No e2e test folder found" in result.output


def test_missing_stories_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, output = r2("story", "list")
    assert code == 1
    assert "Stories folder not found" in output
