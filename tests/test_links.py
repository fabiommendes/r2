from pathlib import Path

from robin.links import Link, extract_links, is_binary, link_from_read


def make_files(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")


def test_extracts_ranges_lines_and_plain_paths(tmp_path: Path) -> None:
    make_files(tmp_path, "src/app.py", "README.md", "a.toml")
    text = "See `src/app.py:20-56`, README.md:3 and ./a.toml."
    assert extract_links(text, tmp_path) == [
        Link(tmp_path / "src/app.py", 20, 56),
        Link(tmp_path / "README.md", 3, 3),
        Link(tmp_path / "a.toml"),
    ]


def test_ignores_missing_files_urls_and_repeats(tmp_path: Path) -> None:
    make_files(tmp_path, "x.py")
    text = "missing.py https://example.com/x.py x.py x.py"
    assert extract_links(text, tmp_path) == [Link(tmp_path / "x.py")]


def test_label_is_relative_to_root(tmp_path: Path) -> None:
    link = Link(tmp_path / "src/app.py", 20, 56)
    assert link.label(tmp_path) == "src/app.py:20-56"
    assert Link(tmp_path / "a.py", 3, 3).label(tmp_path) == "a.py:3"


def test_link_from_read() -> None:
    assert link_from_read({"file_path": "/a.py"}) == Link(Path("/a.py"))
    assert link_from_read({"file_path": "/a.py", "offset": 10, "limit": 5}) == Link(
        Path("/a.py"), 10, 14
    )
    assert link_from_read({}) is None


def test_is_binary(tmp_path: Path) -> None:
    text, binary = tmp_path / "a.txt", tmp_path / "a.png"
    text.write_text("hello\n")
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0")
    assert not is_binary(text)
    assert is_binary(binary)
