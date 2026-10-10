//! Example-based tests. See tests/examples/roman/README.md for the role of
//! each test in the baseline.

use roman::{from_roman, to_roman};

const KNOWN_VALUES: [(u32, &str); 10] = [
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
];

#[test]
fn to_roman_known_values() {
    for (n, numeral) in KNOWN_VALUES {
        assert_eq!(to_roman(n).unwrap(), numeral);
    }
}

#[test]
fn to_roman_returns_string() {
    assert!(to_roman(5).is_ok());
}

#[test]
fn from_roman_iv() {
    assert_eq!(from_roman("IV"), Ok(4));
}

#[test]
fn roundtrip_small() {
    for n in 1..=10 {
        assert_eq!(from_roman(&to_roman(n).unwrap()), Ok(n));
    }
}

#[test]
fn to_roman_rejects_zero() {
    assert!(to_roman(0).is_err());
}

#[test]
fn to_roman_rejects_4000() {
    assert!(to_roman(4000).is_err());
}

#[test]
fn from_roman_rejects_empty() {
    assert!(from_roman("").is_err());
}

#[test]
fn from_roman_rejects_invalid_symbol() {
    assert!(from_roman("ABC").is_err());
}

#[test]
fn from_roman_rejects_out_of_range() {
    assert!(from_roman("MMMM").is_err());
}

#[test]
fn from_roman_rejects_non_canonical() {
    for numeral in ["IIII", "IC", "VX"] {
        assert!(from_roman(numeral).is_err());
    }
}
