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


def test_theme_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    Config(theme="nord").save(path)
    assert Config.load(path).theme == "nord"
    path.write_text('{"theme": 3}')
    assert Config.load(path).theme is None
