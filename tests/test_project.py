from pathlib import Path

from robin.links import Link
from robin.project import Projects


def test_contexts_are_shared_by_git_root(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "src").mkdir()
    projects = Projects()
    assert projects.get(tmp_path / "src") is projects.get(tmp_path)
    assert projects.get(tmp_path).root == tmp_path


def test_new_links_go_on_top_without_duplicates(tmp_path: Path) -> None:
    context = Projects().get(tmp_path)
    a, b, c = (Link(tmp_path / name) for name in "abc")
    context.add_links([a, b])
    context.add_links([c, a])
    assert context.links == [c, a, b]


def test_git_ignored(tmp_path: Path) -> None:
    import subprocess

    from robin.views.project import git_ignored

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("build/\n*.log\n")
    paths = [tmp_path / name for name in ("build", "app.log", "src")]
    for path in paths:
        path.mkdir()
    assert git_ignored(paths) == {tmp_path / "build", tmp_path / "app.log"}
