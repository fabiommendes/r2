"""
Tests for the `r2 issue` and `r2 adr` command groups (dev/spec/cli.md).

They drive the root app in-process, in a temporary project with a .git
folder so the project root is found, and assert on the files on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import app
from r2.core import adrs, issues

runner = CliRunner()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("R2_AGENT", raising=False)
    monkeypatch.setenv("R2_AUTHOR", "claude")
    return tmp_path


def run(*args: str, input: str | None = None):
    return runner.invoke(app, list(args), input=input)


def new_issue(title: str, *args: str) -> Path:
    result = run("issue", "new", title, *args)
    assert result.exit_code == 0, result.output
    return Path(result.output.strip())


#
# new
#
def test_new_issue_writes_the_file_and_prints_its_path(project: Path) -> None:
    path = new_issue("Preview loses the cursor", "--tag", "tui, preview")
    assert path == Path("dev/issues/preview-loses-the-cursor.md")
    issue = issues.load(path)
    assert issue.title == "Preview loses the cursor"
    assert issue.status == "backlog"
    assert issue.meta["tags"] == ["tui", "preview"]
    assert issue.meta["creator"] == "claude"


def test_new_issue_reads_the_body_from_stdin(project: Path) -> None:
    result = run("issue", "new", "T", "--body", "-", input="Line one.\n\nTwo.\n")
    path = Path(result.output.strip())
    assert issues.load(path).description == "Line one.\n\nTwo."


def test_new_issue_never_reuses_a_name(project: Path) -> None:
    assert new_issue("Same") != new_issue("Same")


def test_new_adrs_are_numbered(project: Path) -> None:
    run("adr", "new", "Use flock")
    result = run("adr", "new", "Use YAML")
    assert result.output.strip() == "dev/adr/0002-use-yaml.md"
    assert adrs.load(Path("dev/adr/0002-use-yaml.md")).status == "proposed"


def test_by_beats_the_environment(project: Path) -> None:
    path = new_issue("T", "--by", "fabio")
    assert issues.load(path).meta["creator"] == "fabio"


#
# list, show
#
def test_list_hides_closed_threads_unless_asked(project: Path) -> None:
    new_issue("Open one")
    done = new_issue("Done one")
    run("issue", "status", done.stem, "completed")

    assert run("issue", "list").output == "open-one  backlog  Open one\n"
    assert len(run("issue", "list", "--all").output.splitlines()) == 2
    assert run("issue", "list", "--status", "completed").output == (
        "done-one  completed  Done one\n"
    )


def test_list_json(project: Path) -> None:
    new_issue("One", "--tag", "x")
    [data] = json.loads(run("--json", "issue", "list").output)
    assert data["id"] == "one"
    assert data["meta"]["tags"] == ["x"]


def test_show_prints_the_file(project: Path) -> None:
    path = new_issue("One")
    assert run("issue", "show", "on").output == path.read_text()


def test_show_by_number(project: Path) -> None:
    run("adr", "new", "Use flock")
    assert "# Use flock" in run("adr", "show", "1").output


def test_ambiguous_prefix_is_an_error(project: Path) -> None:
    new_issue("Alpha one")
    new_issue("Alpha two")
    result = run("issue", "show", "alpha")
    assert result.exit_code == 1
    assert "alpha-one, alpha-two" in result.output


def test_unknown_id_is_an_error(project: Path) -> None:
    result = run("issue", "show", "nope")
    assert result.exit_code == 1
    assert "No issue matches" in result.output


#
# comment, status, advance, supersede
#
def test_comment_appends_with_the_author(project: Path) -> None:
    path = new_issue("One")
    result = run("issue", "comment", "one", "-", input="Found it.\n")
    assert result.exit_code == 0, result.output
    [comment] = issues.load(path).comments
    assert (comment.author, comment.text) == ("claude", "Found it.")


def test_empty_comment_is_an_error(project: Path) -> None:
    new_issue("One")
    assert run("issue", "comment", "one", "  ").exit_code == 1


def test_status_rejects_unknown_statuses(project: Path) -> None:
    path = new_issue("One")
    result = run("issue", "status", "one", "done")
    assert result.exit_code == 1
    assert issues.load(path).status == "backlog"


def test_status_dates_closing(project: Path) -> None:
    path = new_issue("One")
    run("issue", "status", "one", "completed")
    assert "closed" in issues.load(path).meta


def test_advance_follows_the_workflow(project: Path) -> None:
    path = new_issue("One")
    result = run("issue", "advance", "one")
    assert result.exit_code == 0, result.output
    assert issues.load(path).status == "todo"


def test_supersede_marks_both_adrs(project: Path) -> None:
    run("adr", "new", "Old way")
    run("adr", "new", "New way")
    result = run("adr", "supersede", "2", "1")
    assert result.exit_code == 0, result.output

    new = adrs.load(Path("dev/adr/0002-new-way.md"))
    old = adrs.load(Path("dev/adr/0001-old-way.md"))
    assert new.meta["supersedes"] == ["0001-old-way"]
    assert (old.status, old.meta["supersededBy"]) == ("superseded", "0002-new-way")


def test_an_adr_cannot_supersede_itself(project: Path) -> None:
    run("adr", "new", "Way")
    assert run("adr", "supersede", "1", "1").exit_code == 1
