import pytest

from r2.core.reports.frontmatter import title_from_path


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("auth-review", "Auth review"),
        ("oauth/session_notes", "Session notes"),
        ("x", "X"),
    ],
)
def test_title_from_path(path: str, expected: str) -> None:
    assert title_from_path(path) == expected
