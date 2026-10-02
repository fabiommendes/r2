from robin.widgets.preview import faded_rows


def test_fades_both_sides_inside_a_long_file() -> None:
    # Link at lines 20-22 of 100: excerpt 14-28, full context 17-25.
    assert faded_rows(14, 28, 20, 22, 100) == {0, 1, 2, 12, 13, 14}


def test_no_fade_where_the_excerpt_reaches_the_file_edges() -> None:
    # Link at lines 2-3 of 5: the excerpt is the whole file.
    assert faded_rows(1, 5, 2, 3, 5) == set()
    # Near the top only the bottom fades.
    assert faded_rows(1, 10, 4, 4, 50) == {7, 8, 9}
