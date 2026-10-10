//! Core suite: property-based tests. See tests/examples/roman/README.md.

use proptest::prelude::*;
use proptest::test_runner::{Config, RngSeed};
use roman::{from_roman, to_roman, MAX_VALUE, MIN_VALUE};

proptest! {
    #![proptest_config(Config { rng_seed: RngSeed::Fixed(0), ..Config::default() })]

    #[test]
    fn roundtrip(n in MIN_VALUE..=MAX_VALUE) {
        prop_assert_eq!(from_roman(&to_roman(n).unwrap()), Ok(n));
    }

    #[test]
    fn to_roman_uses_only_roman_symbols(n in MIN_VALUE..=MAX_VALUE) {
        prop_assert!(to_roman(n).unwrap().chars().all(|c| "IVXLCDM".contains(c)));
    }
}
