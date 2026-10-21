from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from r2.core.reports.scan import (
    SourceFile,
    confine,
    list_source_files,
    read_source_file,
    stat_files,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path.resolve() / "project"
    folder.mkdir()
    return folder


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A folder next to the project root, which nothing may reach."""
    folder = tmp_path.resolve() / "outside"
    folder.mkdir()
    return folder


def write(root: Path, path: str, content: str | bytes) -> None:
    file = root.joinpath(*path.split("/"))
    file.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        file.write_bytes(content)
    else:
        file.write_text(content, encoding="utf-8")


def read_ok(root: Path, path: str, max_bytes: int | None = None) -> SourceFile:
    result = (
        read_source_file(root, path)
        if max_bytes is None
        else read_source_file(root, path, max_bytes=max_bytes)
    )
    assert isinstance(result, SourceFile), result
    return result


class TestConfine:
    def test_accepts_a_path_inside_the_project(self, root: Path) -> None:
        write(root, "src/a.ts", "x")
        assert confine(root, "src/a.ts") == root / "src" / "a.ts"

    def test_rejects_a_parent_traversal(self, root: Path) -> None:
        assert confine(root, "../../etc/passwd") is None

    def test_rejects_a_traversal_to_a_sibling_that_exists(
        self, root: Path, outside: Path
    ) -> None:
        (outside / "secret").write_text("x")
        assert confine(root, "../outside/secret") is None

    def test_accepts_a_traversal_that_stays_inside(self, root: Path) -> None:
        write(root, "a.ts", "x")
        write(root, "src/b.ts", "x")
        assert confine(root, "src/../a.ts") == root / "a.ts"

    def test_rejects_an_absolute_path_outside_the_project(self, root: Path) -> None:
        assert confine(root, "/etc/passwd") is None

    def test_rejects_a_nul_byte(self, root: Path) -> None:
        assert confine(root, "src/a\0.ts") is None

    def test_rejects_a_symlink_that_leaves_the_project(
        self, root: Path, outside: Path
    ) -> None:
        (outside / "target").write_text("secret")
        (root / "escape").symlink_to(outside / "target")
        assert confine(root, "escape") is None

    def test_rejects_a_new_file_below_a_symlinked_folder_that_leaves(
        self, root: Path, outside: Path
    ) -> None:
        (root / "link").symlink_to(outside, target_is_directory=True)
        assert confine(root, "link/new.txt") is None

    def test_accepts_a_symlink_that_stays_inside(self, root: Path) -> None:
        write(root, "real.ts", "x")
        (root / "alias.ts").symlink_to(root / "real.ts")
        assert confine(root, "alias.ts") == root / "real.ts"

    def test_accepts_a_file_that_does_not_exist_yet_inside_the_project(
        self, root: Path
    ) -> None:
        assert confine(root, "src/new.ts") == root / "src" / "new.ts"

    def test_does_not_mistake_a_sibling_with_the_same_prefix_for_inside(
        self, root: Path
    ) -> None:
        sibling = root.parent / "project-evil"
        sibling.mkdir()
        (sibling / "x").write_text("x")
        assert confine(root, "../project-evil/x") is None


class TestReadSourceFile:
    def test_reads_lines_and_infers_the_language(self, root: Path) -> None:
        write(root, "src/a.ts", "const a = 1\nconst b = 2\n")
        file = read_ok(root, "src/a.ts")
        assert file.lines == ["const a = 1", "const b = 2"]
        assert file.lang == "typescript"
        assert file.truncated is False

    def test_reports_path_size_and_modification_time(self, root: Path) -> None:
        write(root, "a.py", "x = 1\n")
        file = read_ok(root, "a.py")
        assert file.path == "a.py"
        assert file.size == 6
        assert isinstance(file.modified, datetime)

    def test_counts_lines_the_way_an_editor_does(self, root: Path) -> None:
        write(root, "no-break.txt", "one\ntwo")
        write(root, "with-break.txt", "one\ntwo\n")
        assert read_ok(root, "no-break.txt").lines == ["one", "two"]
        assert read_ok(root, "with-break.txt").lines == ["one", "two"]

    def test_keeps_a_blank_last_line(self, root: Path) -> None:
        write(root, "a.txt", "one\n\n")
        assert read_ok(root, "a.txt").lines == ["one", ""]

    def test_reads_crlf_as_line_breaks(self, root: Path) -> None:
        write(root, "a.txt", b"one\r\ntwo\r\n")
        assert read_ok(root, "a.txt").lines == ["one", "two"]

    def test_handles_an_empty_file(self, root: Path) -> None:
        write(root, "empty.ts", "")
        assert read_ok(root, "empty.ts").lines == [""]

    def test_hashes_the_content_not_the_path(self, root: Path) -> None:
        write(root, "a.ts", "same\n")
        write(root, "b.ts", "same\n")
        write(root, "c.ts", "other\n")
        assert read_ok(root, "a.ts").hash == read_ok(root, "b.ts").hash
        assert read_ok(root, "a.ts").hash != read_ok(root, "c.ts").hash
        assert read_ok(root, "a.ts").hash == hashlib.sha256(b"same\n").hexdigest()

    def test_leaves_an_unknown_extension_without_a_language(self, root: Path) -> None:
        write(root, "notes.unknownext", "text\n")
        assert read_ok(root, "notes.unknownext").lang is None

    def test_refuses_a_binary_file(self, root: Path) -> None:
        write(root, "logo.png", bytes([0x89, 0x50, 0x4E, 0x47, 0x00, 0x01]))
        assert read_source_file(root, "logo.png") == "binary"

    def test_refuses_bytes_that_are_not_utf8_even_with_no_nul_in_them(
        self, root: Path
    ) -> None:
        write(root, "blob.bin", bytes([0xFF, 0xFE, 0x41, 0xFF, 0x80]))
        assert read_source_file(root, "blob.bin") == "binary"

    def test_keeps_a_utf8_file_whose_last_character_is_cut_by_the_cap(
        self, root: Path
    ) -> None:
        write(root, "accents.txt", "café au lait\n")
        file = read_ok(root, "accents.txt", max_bytes=4)
        assert file.lines == ["caf"]
        assert file.truncated

    def test_reports_a_missing_file_a_directory_and_an_escape_the_same_way(
        self, root: Path
    ) -> None:
        (root / "src").mkdir()
        assert read_source_file(root, "nope.ts") == "missing"
        assert read_source_file(root, "src") == "missing"
        assert read_source_file(root, "../../etc/passwd") == "missing"

    def test_refuses_a_symlink_out_of_the_project(
        self, root: Path, outside: Path
    ) -> None:
        (outside / "secret").write_text("secret\n")
        (root / "escape.ts").symlink_to(outside / "secret")
        assert read_source_file(root, "escape.ts") == "missing"

    def test_truncates_at_a_line_boundary_and_says_so(self, root: Path) -> None:
        write(root, "big.ts", "aaaa\nbbbb\ncccc\ndddd\n")
        file = read_ok(root, "big.ts", max_bytes=12)
        assert file.lines == ["aaaa", "bbbb"]
        assert file.truncated
        assert file.size == 20

    def test_a_file_exactly_at_the_cap_is_not_truncated(self, root: Path) -> None:
        write(root, "exact.ts", "aaaa\nbbbb\n")
        file = read_ok(root, "exact.ts", max_bytes=10)
        assert file.lines == ["aaaa", "bbbb"]
        assert not file.truncated


class TestListSourceFiles:
    def test_lists_regular_project_files_and_skips_ignored_directories(
        self, root: Path
    ) -> None:
        write(root, "src/a.ts", "a\n")
        write(root, "src/nested/b.ts", "b\n")
        write(root, ".github/workflows/ci.yml", "name: ci\n")
        write(root, "node_modules/pkg/index.js", "dep\n")
        write(root, ".reportlab/reports/x.md", "report\n")
        write(root, ".git/HEAD", "ref\n")

        files = list_source_files(root)
        assert [f.path for f in files] == [
            ".github/workflows/ci.yml",
            "src/a.ts",
            "src/nested/b.ts",
        ]
        assert isinstance(files[0].modified, datetime)
        assert next(f for f in files if f.path == "src/a.ts").size == 2

    def test_leaves_out_symlinks(self, root: Path, outside: Path) -> None:
        write(root, "real.ts", "x\n")
        (outside / "secret").write_text("secret\n")
        (root / "link.ts").symlink_to(outside / "secret")
        assert [f.path for f in list_source_files(root)] == ["real.ts"]

    def test_an_empty_project_has_no_files(self, root: Path) -> None:
        assert list_source_files(root) == []


class TestStatFiles:
    def test_answers_a_batch_leaving_out_what_is_not_a_file(self, root: Path) -> None:
        write(root, "src/a.ts", "a\n")
        write(root, "src/b.ts", "bb\n")
        found = stat_files(
            root, ["src/a.ts", "src/b.ts", "src/gone.ts", "src", "../../etc/passwd"]
        )
        assert sorted(found) == ["src/a.ts", "src/b.ts"]
        assert found["src/b.ts"].size == 3
        assert isinstance(found["src/a.ts"].modified, datetime)

    def test_keys_by_the_path_as_it_was_asked_for(self, root: Path) -> None:
        write(root, "src/a.ts", "a\n")
        found = stat_files(root, ["./src/a.ts"])
        assert list(found) == ["./src/a.ts"]
        assert found["./src/a.ts"].path == "./src/a.ts"

    def test_leaves_out_a_symlink_that_leaves_the_project(
        self, root: Path, outside: Path
    ) -> None:
        (outside / "secret").write_text("secret\n")
        (root / "escape").symlink_to(outside / "secret")
        assert stat_files(root, ["escape"]) == {}

    def test_returns_nothing_for_an_empty_batch(self, root: Path) -> None:
        assert stat_files(root, []) == {}
