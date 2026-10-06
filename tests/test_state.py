from pathlib import Path

import pytest

from r2.core.state import DEFAULT_DRAWER_WIDTH, UIState


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "r2" / "tui.json"
    UIState(drawer_widths={"live": 42}).save(path)
    state = UIState.load(path)
    assert state.drawer_width("live") == 42
    assert state.drawer_width("docs") == DEFAULT_DRAWER_WIDTH


def test_broken_file_falls_back_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "tui.json"
    for content in ("not json", "[]", '{"drawer_widths": {"live": "wide"}}'):
        path.write_text(content)
        assert UIState.load(path) == UIState()
    assert UIState.load(tmp_path / "missing.json") == UIState()


def test_theme_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "tui.json"
    UIState(theme="nord").save(path)
    assert UIState.load(path).theme == "nord"
    path.write_text('{"theme": 3}')
    assert UIState.load(path).theme is None


def test_default_location_is_the_state_dir(xdg: Path) -> None:
    UIState(theme="nord").save()
    assert (xdg / "state" / "r2" / "tui.json").is_file()
    assert not (xdg / "config" / "r2").exists()


def test_load_copies_the_old_r2_config_json_once(xdg: Path) -> None:
    legacy = xdg / "config" / "r2" / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"theme": "nord"}')

    assert UIState.load().theme == "nord"
    assert (xdg / "state" / "r2" / "tui.json").read_text() == '{"theme": "nord"}'

    legacy.write_text('{"theme": "dracula"}')
    assert UIState.load().theme == "nord"


def test_old_r2_file_wins_over_robin(xdg: Path) -> None:
    for name, theme in (("r2", "nord"), ("robin", "dracula")):
        legacy = xdg / "config" / name / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(f'{{"theme": "{theme}"}}')
    assert UIState.load().theme == "nord"


def test_load_copies_legacy_robin_config(xdg: Path) -> None:
    legacy = xdg / "config" / "robin" / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"theme": "nord"}')
    assert UIState.load().theme == "nord"


def test_load_without_any_file_creates_nothing(xdg: Path) -> None:
    assert UIState.load() == UIState()
    assert not (xdg / "state" / "r2").exists()
