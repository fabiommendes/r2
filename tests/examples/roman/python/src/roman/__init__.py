"""
Convert integers in 1..3999 to Roman numerals and back.
"""

NUMERALS = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]

VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

MIN_VALUE = 1
MAX_VALUE = 3999


def to_roman(n: int) -> str:
    if not MIN_VALUE <= n <= MAX_VALUE:
        raise ValueError(f"{n} is out of range {MIN_VALUE}..{MAX_VALUE}")

    parts = []
    for value, symbol in NUMERALS:
        count, n = divmod(n, value)
        parts.append(symbol * count)
    return "".join(parts)


def from_roman(s: str) -> int:
    if not s:
        raise ValueError("empty numeral")

    total = 0
    for i, ch in enumerate(s):
        if ch not in VALUES:
            raise ValueError(f"invalid symbol {ch!r}")
        value = VALUES[ch]
        if i + 1 < len(s) and VALUES.get(s[i + 1], 0) > value:
            total -= value
        else:
            total += value

    if not MIN_VALUE <= total <= MAX_VALUE:
        raise ValueError(f"{s!r} is out of range {MIN_VALUE}..{MAX_VALUE}")
    if to_roman(total) != s:
        raise ValueError(f"{s!r} is not in canonical form")
    return total
