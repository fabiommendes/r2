"""
Example-based tests. See tests/examples/roman/README.md for the role of each
test in the baseline.
"""

import pytest

from roman import from_roman, to_roman

KNOWN_VALUES = [
    (1, "I"),
    (4, "IV"),
    (9, "IX"),
    (14, "XIV"),
    (40, "XL"),
    (90, "XC"),
    (400, "CD"),
    (900, "CM"),
    (1994, "MCMXCIV"),
    (3999, "MMMCMXCIX"),
]


def test_to_roman_known_values() -> None:
    for n, numeral in KNOWN_VALUES:
        assert to_roman(n) == numeral


def test_to_roman_returns_str() -> None:
    assert isinstance(to_roman(5), str)


def test_from_roman_iv() -> None:
    assert from_roman("IV") == 4


def test_roundtrip_small() -> None:
    for n in range(1, 11):
        assert from_roman(to_roman(n)) == n


def test_to_roman_rejects_zero() -> None:
    with pytest.raises(ValueError):
        to_roman(0)


def test_to_roman_rejects_4000() -> None:
    with pytest.raises(ValueError):
        to_roman(4000)


def test_from_roman_rejects_empty() -> None:
    with pytest.raises(ValueError):
        from_roman("")


def test_from_roman_rejects_invalid_symbol() -> None:
    with pytest.raises(ValueError):
        from_roman("ABC")


def test_from_roman_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        from_roman("MMMM")


def test_from_roman_rejects_non_canonical() -> None:
    for numeral in ["IIII", "IC", "VX"]:
        with pytest.raises(ValueError):
            from_roman(numeral)
