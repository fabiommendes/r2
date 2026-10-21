import pytest

from r2.core.reports.model import Ref
from r2.core.reports.refs import RefError, format_ref, normalize_repo_path, parse_ref


def dump(ref: Ref) -> dict[str, object]:
    return ref.model_dump(exclude_none=True, by_alias=True)


def test_parses_a_whole_file() -> None:
    assert dump(parse_ref("src/auth/session.py")) == {"path": "src/auth/session.py"}


def test_parses_a_single_line() -> None:
    assert dump(parse_ref("a.ts:42")) == {"path": "a.ts", "start": 42}


def test_parses_a_line_and_column() -> None:
    assert dump(parse_ref("a.ts:42:7")) == {"path": "a.ts", "start": 42, "column": 7}


def test_parses_a_range() -> None:
    assert dump(parse_ref("a.ts:10-40")) == {"path": "a.ts", "start": 10, "end": 40}


def test_drops_a_range_that_is_one_line() -> None:
    assert dump(parse_ref("a.ts:10-10")) == {"path": "a.ts", "start": 10}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a.ts#L42", {"path": "a.ts", "start": 42}),
        ("a.ts#L10-40", {"path": "a.ts", "start": 10, "end": 40}),
        ("a.ts#L10-L40", {"path": "a.ts", "start": 10, "end": 40}),
    ],
)
def test_still_reads_the_older_form(text: str, expected: dict[str, object]) -> None:
    assert dump(parse_ref(text)) == expected


def test_normalizes_redundant_segments() -> None:
    assert parse_ref("./src//a.ts:1").path == "src/a.ts"


@pytest.mark.parametrize(
    "text",
    [
        "/etc/passwd",  # absolute path
        "../../.ssh/id_rsa",  # parent segment
        "src/../../x.ts",  # parent segment in the middle
        "C:\\Windows\\win.ini",  # windows absolute path
        "a.ts:0",  # zero line
        "a.ts:40-10",  # inverted range
        "a.ts:40:0",  # zero column
        ":42",  # no path
        "",  # empty
    ],
)
def test_rejects(text: str) -> None:
    with pytest.raises(RefError):
        parse_ref(text)


def test_error_messages_say_what_is_wrong() -> None:
    with pytest.raises(RefError, match="must stay inside the repository"):
        parse_ref("/etc/passwd")
    with pytest.raises(RefError, match="ref has no path"):
        parse_ref(":42")
    with pytest.raises(RefError, match="empty ref"):
        parse_ref("  ")
    with pytest.raises(RefError, match="inverted line range"):
        parse_ref("a.ts:40-10")


@pytest.mark.parametrize("text", ["a.ts", "a.ts:42", "a.ts:42:7", "a.ts:10-40"])
def test_round_trips_through_format_ref(text: str) -> None:
    assert format_ref(parse_ref(text)) == text


def test_formats_the_older_form_into_the_canonical_one() -> None:
    assert format_ref(parse_ref("a.ts#L10-40")) == "a.ts:10-40"


def test_normalize_repo_path() -> None:
    assert normalize_repo_path("a\\b//c/./d.py") == "a/b/c/d.py"
    assert normalize_repo_path("a/\0b") is None
    assert normalize_repo_path("a/..") is None
