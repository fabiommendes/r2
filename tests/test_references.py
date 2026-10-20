"""Files named in the text of a document."""

from pathlib import Path

from r2.core.references import resolve_reference


def project(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    for name in ("r2/core/links.py", "dev/adr/0001-use-python.md", "dev/issues/fix.md"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("")
    return tmp_path / "dev" / "adr" / "0001-use-python.md"


def test_paths_resolve_from_the_project_root_or_the_document(tmp_path: Path) -> None:
    document = project(tmp_path)
    links = tmp_path / "r2" / "core" / "links.py"
    assert resolve_reference("r2/core/links.py", document) == links
    assert resolve_reference("r2/core/links.py:10-20", document) == links
    assert resolve_reference("../issues/fix.md", document) == (
        tmp_path / "dev" / "issues" / "fix.md"
    )


def test_a_bare_stem_names_a_thread(tmp_path: Path) -> None:
    document = project(tmp_path)
    assert resolve_reference("fix", document) == tmp_path / "dev" / "issues" / "fix.md"
    assert resolve_reference("0001-use-python", document) == document


def test_text_that_names_no_file_resolves_to_nothing(tmp_path: Path) -> None:
    document = project(tmp_path)
    for ref in ("r2/core/missing.py", "kind", "x = 1", "--json"):
        assert resolve_reference(ref, document) is None
