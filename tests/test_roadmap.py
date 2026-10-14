"""
Tests for `r2 roadmap` and `r2 changelog --draft` (dev/spec/roadmap.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from r2.cli.app import app
from r2.core import issues, roadmap

runner = CliRunner()


def issue_text(
    title: str,
    status: str = "backlog",
    milestone: str | None = None,
    kind: str | None = None,
) -> str:
    lines = ["---", "type: issue", f"status: {status}"]
    if kind:
        lines.append(f"kind: {kind}")
    if milestone is not None:
        lines.append(f"milestone: {milestone}")
    return "\n".join([*lines, "---", "", f"# {title}", ""])


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("R2_AGENT", raising=False)
    folder = tmp_path / issues.FOLDER
    folder.mkdir(parents=True)
    files = {
        "zeta": issue_text("Zeta", milestone="0.10.0"),
        "alpha": issue_text("Alpha [beta]", "in_progress", milestone="0.9.0"),
        "loose": issue_text("No milestone"),
        "done": issue_text("Done", "completed", "0.9.0", "enhancement"),
        "fix": issue_text("Fixed bug", "completed", "0.9.0", "defect"),
        "chore": issue_text("Chore", "completed", "0.9.0", "task"),
        "dropped": issue_text("Dropped", "wont_fix", "0.9.0", "enhancement"),
    }
    for slug, text in files.items():
        (folder / f"{slug}.md").write_text(text)
    return tmp_path


def test_milestones_sort_as_versions() -> None:
    names = ["0.10.0", "M10", "0.9.0", "m2", "M3-review", "1.0", "0.9.1"]
    assert sorted(names, key=roadmap.milestone_key) == [
        "0.9.0",
        "0.9.1",
        "0.10.0",
        "1.0",
        "m2",
        "M3-review",
        "M10",
    ]


def test_milestone_reads_yaml_scalars_as_text() -> None:
    issue = issues.parse(issue_text("T", milestone="2"))
    assert roadmap.milestone(issue) == "2"
    assert roadmap.milestone(issues.parse(issue_text("T", milestone="''"))) is None


def test_roadmap_groups_open_issues_by_milestone(project: Path) -> None:
    text = roadmap.render_roadmap(roadmap.load(project / issues.FOLDER))
    assert text.startswith(roadmap.ROADMAP_HEADER)
    body = text.removeprefix(roadmap.ROADMAP_HEADER)
    assert body == (
        "\n## 0.9.0\n\n"
        "- [Alpha \\[beta\\]](dev/issues/alpha.md)\n"
        "\n## 0.10.0\n\n"
        "- [Zeta](dev/issues/zeta.md)\n"
    )


def test_roadmap_without_milestones() -> None:
    found = {"a": issues.parse(issue_text("A"))}
    text = roadmap.render_roadmap(found)
    assert text == roadmap.ROADMAP_HEADER + "\n" + roadmap.NO_MILESTONES


def test_changelog_groups_completed_issues_by_kind(project: Path) -> None:
    found = roadmap.load(project / issues.FOLDER)
    sections = roadmap.changelog_sections(found, "0.9.0")
    assert [(s.title, [slug for slug, _ in s.issues]) for s in sections] == [
        ("Added", ["done"]),
        ("Fixed", ["fix"]),
        ("Other", ["chore"]),
    ]
    assert roadmap.render_changelog("0.9.0", sections) == (
        "## [0.9.0]\n\n"
        "### Added\n\n- Done (`done`)\n\n"
        "### Fixed\n\n- Fixed bug (`fix`)\n\n"
        "### Other\n\n- Chore (`chore`)\n"
    )


def test_cli_writes_and_checks_the_roadmap(project: Path) -> None:
    path = project / roadmap.FILE
    result = runner.invoke(app, ["roadmap", "--check"])
    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert not path.exists()

    result = runner.invoke(app, ["roadmap"])
    assert result.exit_code == 0, result.output
    assert "Wrote ROADMAP.md" in result.output
    assert "[Zeta](dev/issues/zeta.md)" in path.read_text()

    result = runner.invoke(app, ["roadmap", "--check"])
    assert result.exit_code == 0, result.output
    assert "up to date" in result.output

    (project / issues.FOLDER / "zeta.md").write_text(
        issue_text("Zeta", "completed", "0.10.0")
    )
    before = path.read_text()
    result = runner.invoke(app, ["roadmap", "--check"])
    assert result.exit_code == 1
    assert "out of date" in result.output
    assert path.read_text() == before

    assert runner.invoke(app, ["roadmap"]).exit_code == 0
    assert "Zeta" not in path.read_text()


def test_cli_changelog_draft(project: Path) -> None:
    result = runner.invoke(app, ["changelog", "--draft", "0.9.0"])
    assert result.exit_code == 0, result.output
    assert "## [0.9.0]" in result.output
    assert "- Fixed bug (`fix`)" in result.output
    assert "Dropped" not in result.output
    assert "1 open issue(s) in 0.9.0 left out: alpha." in result.output


def test_cli_changelog_json(project: Path) -> None:
    result = runner.invoke(app, ["--json", "changelog", "--draft", "0.9.0"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["milestone"] == "0.9.0"
    assert data["sections"][0] == {
        "title": "Added",
        "issues": [{"id": "done", "title": "Done", "kind": "enhancement"}],
    }


def test_cli_changelog_unknown_milestone(project: Path) -> None:
    result = runner.invoke(app, ["changelog", "--draft", "2.0"])
    assert result.exit_code == 1
    assert "known: 0.9.0, 0.10.0" in result.output


def test_cli_changelog_needs_draft(project: Path) -> None:
    assert runner.invoke(app, ["changelog"]).exit_code == 2
