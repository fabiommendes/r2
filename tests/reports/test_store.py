from __future__ import annotations

import json
import os

import pytest

from r2.core.reports.model import FindingMark, ReviewMarks
from r2.core.reports.store import ReportStore, parse_marks, safe_report_path
from tests.reports.repo import Repo, set_mtime


@pytest.fixture
def store(repo: Repo) -> ReportStore:
    return ReportStore(repo.project)


class TestReading:
    def test_uses_the_frontmatter_title(self, repo: Repo, store: ReportStore) -> None:
        repo.write_report("auth", "---\ntitle: Auth flow\nkind: review\n---\n\nbody\n")
        document = store.read("auth")
        assert document is not None
        assert (document.title, document.kind) == ("Auth flow", "review")

    def test_falls_back_to_the_first_heading(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("auth", "# Something happened\n\nbody\n")
        document = store.read("auth")
        assert document is not None
        assert document.title == "Something happened"

    def test_falls_back_to_the_filename(self, repo: Repo, store: ReportStore) -> None:
        repo.write_report("nested/session-notes", "no heading here\n")
        document = store.read("nested/session-notes")
        assert document is not None
        assert (document.title, document.kind) == ("Session notes", "note")

    def test_carries_frontmatter_diagnostics_alongside_render_diagnostics(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report(
            "broken", "---\ntitle: [a]\n---\n\n```rl:finding\nno severity\n```\n"
        )
        document = store.read("broken")
        assert document is not None
        assert [d.field for d in document.rendered.diagnostics] == [
            "title",
            "severity",
        ]

    def test_returns_none_for_a_report_that_does_not_exist(
        self, store: ReportStore
    ) -> None:
        assert store.read("missing") is None

    def test_returns_none_for_a_path_that_escapes(self, store: ReportStore) -> None:
        assert store.read("../config") is None

    def test_rereads_after_the_file_changes(
        self, repo: Repo, store: ReportStore
    ) -> None:
        file = repo.write_report("a", "first\n")
        first = store.read("a")
        assert first is not None
        assert len(first.rendered.nodes) == 1
        file.write_text("first\n\nsecond\n")
        second = store.read("a")
        assert second is not None
        assert len(second.rendered.nodes) == 2

    def test_rereads_a_same_size_change_with_a_new_mtime(
        self, repo: Repo, store: ReportStore
    ) -> None:
        file = repo.write_report("a", "# One\n")
        set_mtime(file, 1_000_000)
        assert store.read("a") is not None
        file.write_text("# Two\n")
        set_mtime(file, 1_000_050)
        document = store.read("a")
        assert document is not None
        assert document.title == "Two"

    def test_forget_drops_the_cached_document(
        self, repo: Repo, store: ReportStore
    ) -> None:
        file = repo.write_report("a", "# One\n")
        set_mtime(file, 1_000_000)
        assert store.read("a") is not None
        file.write_text("# Two\n")
        set_mtime(file, 1_000_000)
        store.forget("a")
        document = store.read("a")
        assert document is not None
        assert document.title == "Two"

    def test_a_report_deleted_after_being_read_is_gone(
        self, repo: Repo, store: ReportStore
    ) -> None:
        file = repo.write_report("a", "one\n")
        assert store.read("a") is not None
        file.unlink()
        assert store.read("a") is None


class TestSummaries:
    def test_newest_first_including_nested_reports(
        self, repo: Repo, store: ReportStore
    ) -> None:
        set_mtime(repo.write_report("old", "old\n"), 1_000_000)
        set_mtime(repo.write_report("group/new", "new\n"), 1_000_100)
        assert [s.path for s in store.summaries()] == ["group/new", "old"]

    def test_summarizes_findings_and_their_highest_severity(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report(
            "review",
            "```rl:finding severity=low\nminor\n```\n\n"
            "```rl:finding severity=high\nmajor\n```\n",
        )
        summary = store.summaries()[0]
        assert summary.findings == 2
        assert summary.severity == "high"
        assert not summary.open

    def test_a_report_without_findings_has_no_severity(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("plain", "text\n")
        summary = store.summaries()[0]
        assert (summary.findings, summary.severity) == (0, None)

    def test_marks_a_report_with_an_unterminated_block_as_open(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("live", "```rl:finding severity=high\nstill writing")
        assert store.summaries()[0].open

    def test_ignores_files_that_are_not_reports(
        self, repo: Repo, store: ReportStore
    ) -> None:
        (repo.project.reports / "notes.txt").write_text("ignored")
        assert store.summaries() == []

    def test_ignores_hidden_files_and_folders(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report(".draft", "x\n")
        repo.write_report(".hidden/inner", "x\n")
        repo.write_report("shown", "x\n")
        assert [s.path for s in store.summaries()] == ["shown"]

    def test_a_sidecar_is_not_a_report(self, repo: Repo, store: ReportStore) -> None:
        repo.write_report("a", "body\n")
        store.write_marks("a", ReviewMarks(read="2026-09-30T15:00:00-03:00"))
        assert [s.path for s in store.summaries()] == ["a"]


class TestReviewMarks:
    def test_round_trips(self, repo: Repo, store: ReportStore) -> None:
        repo.write_report("a", "body\n")
        store.write_marks(
            "a",
            ReviewMarks(
                read="2026-09-30T15:00:00-03:00",
                findings={"f1": FindingMark(state="accepted", note="ok")},
            ),
        )
        marks = store.read_marks("a")
        assert marks is not None
        assert marks.findings["f1"] == FindingMark(state="accepted", note="ok")
        assert store.summaries()[0].read == "2026-09-30T15:00:00-03:00"

    def test_a_mark_without_a_note_round_trips_without_one(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("a", "body\n")
        store.write_marks("a", ReviewMarks(findings={"f1": FindingMark(state="seen")}))
        marks = store.read_marks("a")
        assert marks is not None
        assert marks.findings["f1"] == FindingMark(state="seen", note=None)

    def test_leaves_no_temporary_file_behind(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("a", "body\n")
        store.write_marks("a", ReviewMarks())
        names = sorted(os.listdir(repo.project.reports))
        assert names == ["a.md", "a.review.json"]

    def test_sidecar_lives_beside_the_report(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("group/a", "body\n")
        store.write_marks("group/a", ReviewMarks(read="2026-09-30T15:00:00Z"))
        sidecar = repo.project.reports / "group" / "a.review.json"
        assert json.loads(sidecar.read_text())["read"] == "2026-09-30T15:00:00Z"

    def test_refuses_to_write_marks_for_a_path_that_escapes(
        self, repo: Repo, store: ReportStore
    ) -> None:
        with pytest.raises(ValueError, match="escapes"):
            store.write_marks("../outside", ReviewMarks())
        assert not (repo.root / ".reportlab" / "outside.review.json").exists()

    def test_discards_marks_with_an_unknown_state(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("a", "body\n")
        (repo.project.reports / "a.review.json").write_text(
            json.dumps({"findings": {"f1": {"state": "maybe"}}})
        )
        marks = store.read_marks("a")
        assert marks is not None
        assert marks.findings == {}

    def test_treats_a_corrupt_sidecar_as_absent(
        self, repo: Repo, store: ReportStore
    ) -> None:
        repo.write_report("a", "body\n")
        (repo.project.reports / "a.review.json").write_text("{ not json")
        assert store.read_marks("a") is None

    def test_no_sidecar_means_no_marks(self, repo: Repo, store: ReportStore) -> None:
        repo.write_report("a", "body\n")
        assert store.read_marks("a") is None
        assert store.summaries()[0].read is None


class TestParseMarks:
    @pytest.mark.parametrize("raw", [None, [], "text", 7], ids=repr)
    def test_anything_but_an_object_is_empty(self, raw: object) -> None:
        assert parse_marks(raw) == ReviewMarks()

    def test_drops_what_it_does_not_recognize(self) -> None:
        marks = parse_marks(
            {
                "read": 5,
                "findings": {
                    "f1": {"state": "accepted", "note": 3},
                    "f2": {"state": "wat"},
                    "f3": "accepted",
                },
            }
        )
        assert marks.read is None
        assert marks.findings == {"f1": FindingMark(state="accepted", note=None)}

    def test_findings_that_is_not_an_object_leaves_read_alone(self) -> None:
        marks = parse_marks({"read": "2026-09-30T15:00:00Z", "findings": []})
        assert marks == ReviewMarks(read="2026-09-30T15:00:00Z")


class TestSafeReportPath:
    @pytest.mark.parametrize("path", ["auth", "group/auth", "a/b/c"])
    def test_accepts(self, path: str) -> None:
        assert safe_report_path(path) == path

    @pytest.mark.parametrize(
        "path",
        [
            "../secret",
            "a/../../secret",
            "a/..",
            "",
            "/",
            ".hidden",
            "a/.hidden/b",
            "a/\0b",
            "a\\..\\b",
        ],
    )
    def test_rejects(self, path: str) -> None:
        assert safe_report_path(path) is None

    def test_normalizes_redundant_separators(self) -> None:
        assert safe_report_path("./a//b") == "a/b"

    def test_a_leading_slash_does_not_make_it_absolute(self) -> None:
        assert safe_report_path("/etc/passwd") == "etc/passwd"
