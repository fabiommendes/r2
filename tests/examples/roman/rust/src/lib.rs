//! Convert integers in 1..=3999 to Roman numerals and back.

use std::fmt;

pub const MIN_VALUE: u32 = 1;
pub const MAX_VALUE: u32 = 3999;

const NUMERALS: [(u32, &str); 13] = [
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
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RomanError {
    OutOfRange(i64),
    Empty,
    InvalidSymbol(char),
    NonCanonical(String),
}

impl fmt::Display for RomanError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RomanError::OutOfRange(n) => write!(f, "{n} is out of range {MIN_VALUE}..={MAX_VALUE}"),
            RomanError::Empty => write!(f, "empty numeral"),
            RomanError::InvalidSymbol(ch) => write!(f, "invalid symbol {ch:?}"),
            RomanError::NonCanonical(s) => write!(f, "{s:?} is not in canonical form"),
        }
    }
}

impl std::error::Error for RomanError {}

fn value_of(ch: char) -> Option<i64> {
    match ch {
        'I' => Some(1),
        'V' => Some(5),
        'X' => Some(10),
        'L' => Some(50),
        'C' => Some(100),
        'D' => Some(500),
        'M' => Some(1000),
        _ => None,
    }
}

pub fn to_roman(n: u32) -> Result<String, RomanError> {
    if !(MIN_VALUE..=MAX_VALUE).contains(&n) {
        return Err(RomanError::OutOfRange(n.into()));
    }

    let mut n = n;
    let mut out = String::new();
    for (value, symbol) in NUMERALS {
        let count = n / value;
        n %= value;
        out.push_str(&symbol.repeat(count as usize));
    }
    Ok(out)
}

pub fn from_roman(s: &str) -> Result<u32, RomanError> {
    if s.is_empty() {
        return Err(RomanError::Empty);
    }

    let chars: Vec<char> = s.chars().collect();
    let mut total: i64 = 0;
    for (i, &ch) in chars.iter().enumerate() {
        let value = value_of(ch).ok_or(RomanError::InvalidSymbol(ch))?;
        let next = chars.get(i + 1).and_then(|&c| value_of(c)).unwrap_or(0);
        if next > value {
            total -= value;
        } else {
            total += value;
        }
    }

    if !(i64::from(MIN_VALUE)..=i64::from(MAX_VALUE)).contains(&total) {
        return Err(RomanError::OutOfRange(total));
    }
    let total = total as u32;
    if to_roman(total)? != s {
        return Err(RomanError::NonCanonical(s.to_string()));
    }
    Ok(total)
}
