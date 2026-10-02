from pathlib import Path

from robin.config import DEFAULT_DRAWER_WIDTH, Config


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "robin" / "config.json"
    Config(drawer_widths={"live": 42}).save(path)
    config = Config.load(path)
    assert config.drawer_width("live") == 42
    assert config.drawer_width("docs") == DEFAULT_DRAWER_WIDTH


def test_broken_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    for content in ("not json", "[]", '{"drawer_widths": {"live": "wide"}}'):
        path.write_text(content)
        assert Config.load(path) == Config()
    assert Config.load(tmp_path / "missing.json") == Config()
