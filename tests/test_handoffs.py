"""
Tests for handoff files and `r2 handoff` (dev/spec/handoffs.md).
"""

from __future__ import annotations

import datetime
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import app
from r2.core import handoffs

runner = CliRunner()

HANDOFF = """\
---
type: handoff
status: open
issue: preview-bug
branch: preview-bug
worktree: /tmp/r2-preview-bug
created: 2026-10-14T15:30
creator: claude
---

# Fix the cursor of the preview

## Estado

Done: the cause.

---

## Próximo passo
"""


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git("init", "-q", "-b", "main", cwd=tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("R2_AGENT", raising=False)
    return tmp_path


def write(root: Path, slug: str, text: str = HANDOFF) -> Path:
    path = root / handoffs.FOLDER / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def handoff(slug: str, *, status: str = "open", created: str = "2026-10-14T15:30",
            issue: str | None = None) -> str:  # fmt: skip
    lines = ["---", "type: handoff", f"status: {status}"]
    if issue:
        lines.append(f"issue: {issue}")
    lines += [f"created: {created}", "---", "", f"# Work on {slug}", ""]
    return "\n".join(lines)


def run(*args: str):
    return runner.invoke(app, ["handoff", *args])


#
# Reading
#
def test_parse_reads_the_format_of_the_skill() -> None:
    found = handoffs.parse(HANDOFF, Path("preview-bug.md"))
    assert found.title == "Fix the cursor of the preview"
    assert found.status == "open"
    assert found.issue == "preview-bug"
    assert found.created == datetime.datetime(2026, 10, 14, 15, 30)
    assert found.meta["worktree"] == "/tmp/r2-preview-bug"
    assert found.body.startswith("# Fix the cursor")


def test_parse_is_lenient() -> None:
    found = handoffs.parse("Just notes.\n", Path("some-work.md"), mtime=0)
    assert found.title == "some work"
    assert found.status == "open"
    assert found.created == datetime.datetime.fromtimestamp(0)


def test_set_status_changes_only_the_status_line() -> None:
    taken = handoffs.set_status(HANDOFF, "taken")
    assert taken == HANDOFF.replace("status: open", "status: taken")


def test_set_status_adds_a_missing_status_or_frontmatter() -> None:
    text = "---\ntype: handoff\ncreated: 2026-10-14T15:30\n---\n\n# T\n"
    assert handoffs.set_status(text, "taken").startswith(
        "---\ntype: handoff\nstatus: taken\ncreated:"
    )
    assert handoffs.set_status("# T\n", "taken") == (
        "---\ntype: handoff\nstatus: taken\n---\n\n# T\n"
    )


#
# Folder
#
def test_folder_is_in_the_main_checkout_from_a_worktree(project: Path) -> None:
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
        "--allow-empty", "-m", "init", cwd=project)  # fmt: skip
    worktree = project.parent / "wt"
    git("worktree", "add", "-q", str(worktree), cwd=project)
    expected = project.resolve() / handoffs.FOLDER
    assert handoffs.folder(worktree).resolve() == expected
    assert handoffs.folder(project).resolve() == expected


def test_folder_outside_git_is_in_the_project_root(tmp_path: Path) -> None:
    assert handoffs.folder(tmp_path) == tmp_path / handoffs.FOLDER


#
# list and show
#
def test_list_shows_open_handoffs_most_recent_first(project: Path) -> None:
    write(project, "old", handoff("old", created="2026-10-01T10:00"))
    write(project, "new", handoff("new", created="2026-10-14T10:00"))
    write(project, "done", handoff("done", status="taken"))
    result = run("list")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        "new  open  2026-10-14T10:00  Work on new",
        "old  open  2026-10-01T10:00  Work on old",
    ]
    assert "done  taken" in run("list", "--all").output


def test_list_without_a_folder_prints_nothing(project: Path) -> None:
    result = run("list")
    assert result.exit_code == 0
    assert result.output == ""


def test_show_prints_the_file_and_json(project: Path) -> None:
    write(project, "preview-bug")
    assert run("show", "prev").output == HANDOFF
    data = json.loads(runner.invoke(app, ["--json", "handoff", "show", "prev"]).output)
    assert data["id"] == "preview-bug"
    assert data["status"] == "open"
    assert data["created"] == "2026-10-14T15:30"
    assert data["meta"]["branch"] == "preview-bug"
    assert data["body"].startswith("# Fix the cursor")


def test_show_an_unknown_handoff_fails(project: Path) -> None:
    result = run("show", "nope")
    assert result.exit_code == 1
    assert "No handoff matches" in result.output


#
# take
#
def test_take_marks_the_handoff_and_prints_it(project: Path) -> None:
    path = write(project, "preview-bug")
    result = run("take", "preview-bug")
    assert result.exit_code == 0, result.output
    assert "status: taken" in result.output
    assert path.read_text() == HANDOFF.replace("status: open", "status: taken")
    gitignore = project / handoffs.FOLDER / ".gitignore"
    assert gitignore.read_text() == "*\n"


def test_take_twice_fails(project: Path) -> None:
    write(project, "preview-bug")
    assert run("take", "preview-bug").exit_code == 0
    result = run("take", "preview-bug")
    assert result.exit_code == 1
    assert "is taken" in result.output


def test_take_without_id_takes_the_latest_open(project: Path) -> None:
    write(project, "old", handoff("old", created="2026-10-01T10:00"))
    write(project, "new", handoff("new", created="2026-10-14T10:00"))
    write(project, "newest", handoff("newest", status="taken",
                                     created="2026-10-15T10:00"))  # fmt: skip
    assert "# Work on new" in run("take").output
    assert "# Work on old" in run("take").output
    result = run("take")
    assert result.exit_code == 1
    assert "No open handoff" in result.output


#
# prune
#
def test_prune_removes_taken_old_and_closed_issue_handoffs(project: Path) -> None:
    now = datetime.datetime.now()
    recent = f"{now:%Y-%m-%dT%H:%M}"
    old = f"{now - datetime.timedelta(days=8):%Y-%m-%dT%H:%M}"
    issues_folder = project / "dev" / "issues"
    issues_folder.mkdir(parents=True)
    (issues_folder / "done.md").write_text("---\ntype: issue\nstatus: completed\n---\n")
    (issues_folder / "doing.md").write_text("---\ntype: issue\nstatus: todo\n---\n")
    write(project, "keep", handoff("keep", created=recent, issue="doing"))
    write(project, "unknown", handoff("unknown", created=recent, issue="gone"))
    write(project, "taken", handoff("taken", status="taken", created=recent))
    write(project, "old", handoff("old", created=old))
    write(project, "closed", handoff("closed", created=recent, issue="done"))

    result = run("prune")

    assert result.exit_code == 0, result.output
    left = sorted(p.stem for p in (project / handoffs.FOLDER).glob("*.md"))
    assert left == ["keep", "unknown"]
    assert "Removed closed (issue done is closed)." in result.output
    assert "Removed old (older than 7 days)." in result.output
    assert "Removed taken (taken)." in result.output


def test_prune_days_changes_the_age(project: Path) -> None:
    now = datetime.datetime.now()
    created = f"{now - datetime.timedelta(days=3):%Y-%m-%dT%H:%M}"
    write(project, "work", handoff("work", created=created))
    assert run("prune").exit_code == 0
    assert (project / handoffs.FOLDER / "work.md").exists()
    assert run("prune", "--days", "2").exit_code == 0
    assert not (project / handoffs.FOLDER / "work.md").exists()


def test_prune_without_a_folder_does_nothing(project: Path) -> None:
    result = run("prune")
    assert result.exit_code == 0
    assert "Nothing to prune." in result.output
    assert not (project / handoffs.FOLDER).exists()
