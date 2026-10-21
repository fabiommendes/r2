from r2.core.reports.candidates import candidate_key, detect_candidates
from r2.core.reports.model import Candidate


def kinds(text: str) -> list[str]:
    return [f"{c.kind}:{c.raw}" for c in detect_candidates(text)]


def only(text: str) -> Candidate:
    found = detect_candidates(text)
    assert len(found) == 1
    return found[0]


def test_finds_a_bare_path() -> None:
    assert only("see src/auth/session.py for details").path == "src/auth/session.py"


def test_finds_a_path_with_no_directory() -> None:
    assert only("documented in README.md").path == "README.md"


def test_accepts_the_compiler_and_ripgrep_locator_form() -> None:
    c = only("src/a.ts:42: unexpected token")
    assert (c.path, c.start_line) == ("src/a.ts", 42)


def test_accepts_a_line_range() -> None:
    c = only("look at src/a.ts:10-40 first")
    assert (c.path, c.start_line, c.end_line) == ("src/a.ts", 10, 40)


def test_accepts_a_line_and_column() -> None:
    c = only("src/a.ts:42:7: unexpected token")
    assert (c.path, c.start_line, c.column) == ("src/a.ts", 42, 7)


def test_still_accepts_the_older_locator_form() -> None:
    c = only("look at src/a.ts#L10-40 first")
    assert (c.path, c.start_line, c.end_line) == ("src/a.ts", 10, 40)


def test_stops_the_range_at_a_word() -> None:
    c = only("src/a.ts:42-and then")
    assert (c.raw, c.start_line, c.end_line) == ("src/a.ts:42", 42, None)


def test_drops_trailing_sentence_punctuation() -> None:
    assert only("it lives in src/a.ts.").raw == "src/a.ts"


def test_finds_a_commit_hash_but_not_a_plain_number() -> None:
    assert kinds("fixed in a1b2c3d") == ["commit:a1b2c3d"]
    assert kinds("exactly 1234567 rows") == []


def test_does_not_find_a_commit_inside_a_hyphenated_token() -> None:
    assert kinds("the run 20260930-142501-abcdef1 failed") == []


def test_ignores_urls() -> None:
    assert kinds("https://example.com/a/b.html is unrelated") == []


def test_ignores_email_addresses() -> None:
    assert kinds("mail someone@example.com about it") == []


def test_ignores_decimals_and_version_numbers() -> None:
    assert kinds("took 1.5 seconds on node 24.18.0") == []


def test_reports_offsets_that_splice_out_cleanly() -> None:
    text = "both src/a.ts and src/b.ts changed"
    found = detect_candidates(text)
    assert [text[c.start : c.end] for c in found] == ["src/a.ts", "src/b.ts"]


def test_keys_a_candidate_by_kind_and_raw() -> None:
    assert candidate_key(only("see src/a.ts:4")) == "path:src/a.ts:4"
    assert candidate_key(only("fixed in a1b2c3d")) == "commit:a1b2c3d"


def test_word_characters_are_ascii_as_in_the_original() -> None:
    # `ç` is not a word character, so the path starts right after it.
    assert kinds("see ação/a.ts") == ["path:o/a.ts"]


def test_finds_absolute_home_and_parent_paths() -> None:
    assert only("read /home/me/src/a.py:3 now").path == "/home/me/src/a.py"
    assert only("see ~/notes/todo.md").path == "~/notes/todo.md"
    assert only("in ../lib/b.py").path == "../lib/b.py"
    assert only("or ./a.toml.").path == "./a.toml"


def test_an_absolute_path_inside_a_url_is_not_a_candidate() -> None:
    assert kinds("https://example.com/src/a.py") == []


def test_a_code_span_that_is_a_path_is_a_candidate() -> None:
    from r2.core.reports.candidates import code_span_candidate

    c = code_span_candidate("src/a.py:10-20")
    assert c is not None
    assert (c.kind, c.path, c.start_line, c.end_line) == ("path", "src/a.py", 10, 20)


def test_a_code_span_that_is_a_word_is_a_stem() -> None:
    from r2.core.reports.candidates import code_span_candidate

    c = code_span_candidate("issue-flow")
    assert c is not None
    assert (c.kind, c.path) == ("stem", "issue-flow")
    for text in ("x = 1", "--json", "a b", ""):
        assert code_span_candidate(text) is None
