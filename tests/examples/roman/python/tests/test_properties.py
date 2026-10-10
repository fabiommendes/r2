"""
Core suite: property-based tests. See tests/examples/roman/README.md.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from roman import MAX_VALUE, MIN_VALUE, from_roman, to_roman

numbers = st.integers(MIN_VALUE, MAX_VALUE)


@settings(derandomize=True)
@given(numbers)
def test_roundtrip(n: int) -> None:
    assert from_roman(to_roman(n)) == n


@settings(derandomize=True)
@given(numbers)
def test_to_roman_uses_only_roman_symbols(n: int) -> None:
    assert set(to_roman(n)) <= set("IVXLCDM")
