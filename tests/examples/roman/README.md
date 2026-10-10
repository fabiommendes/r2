# roman: baseline for test analysis

One library, three implementations with the same API and the same test
catalog:

- `to_roman(n)`: integer in 1..3999 to its canonical Roman numeral. Raises
  (or returns an error) outside that range.
- `from_roman(s)`: canonical Roman numeral back to its integer. Rejects
  empty input, unknown symbols, values out of range and non-canonical
  numerals such as `IIII` or `IC`.

| Directory | Toolchain                    | Core suite                     | Other suites                                  |
|-----------|------------------------------|--------------------------------|-----------------------------------------------|
| `python/` | uv, pytest, hypothesis       | `tests/test_properties.py`     | `tests/test_examples.py`                      |
| `rust/`   | cargo, proptest              | `tests/properties.rs`          | `tests/examples.rs`                           |
| `ts/`     | npm, vitest, fast-check, playwright | `tests/unit/properties.test.ts` | `tests/unit/examples.test.ts`, `tests/e2e/convert.spec.ts` |

Run them with:

```sh
cd python && uv run pytest
cd rust && cargo test
cd ts && npm install && npx vitest run && npx playwright test
```

Property tests use a fixed seed, so their coverage is the same on every run.

## Test catalog

The core suite is the property-based tests. Every other test has a planned
role relative to the core. The analysis commands should reproduce this table.

Coverage columns: "redundant" means every branch the test runs is already
run by the core. Mutation column: whether the test kills mutants that
survive the core. The core is mutation-weak on purpose: `from_roman`
validates its input with `to_roman`, so a roundtrip cannot see a wrong entry
in the numeral table (for example 900 written as `DCCCC`).

| Test                                | Coverage vs core | Kills core survivors | Role                                  |
|-------------------------------------|------------------|----------------------|---------------------------------------|
| `to_roman_known_values`             | redundant        | yes                  | keep: only test that pins the output  |
| `to_roman_returns_str`              | redundant        | no                   | delete: trivial assertion             |
| `from_roman_iv`                     | redundant        | no                   | delete: one case of the roundtrip     |
| `roundtrip_small`                   | redundant        | no                   | delete: weaker copy of the core       |
| `to_roman_rejects_zero`             | adds             | yes                  | keep                                  |
| `to_roman_rejects_4000`             | adds             | yes                  | overlaps `to_roman_rejects_zero`      |
| `from_roman_rejects_empty`          | adds             | yes                  | keep                                  |
| `from_roman_rejects_invalid_symbol` | adds             | yes                  | keep                                  |
| `from_roman_rejects_out_of_range`   | adds             | yes                  | keep                                  |
| `from_roman_rejects_non_canonical`  | adds             | yes                  | keep                                  |

Test names follow each language's convention (`toRoman known values` in TS,
`to_roman_returns_string` in Rust).

The TS e2e suite runs the library through a demo page (`index.html`,
`src/main.ts`). Its tests are redundant with the core on `src/roman.ts` but
are the only ones that cover `src/main.ts`, so they show redundancy across
test runners.

The mutation column is the design intent and has not been checked with a
mutation tool yet. The coverage column was checked for `python/` with
coverage.py dynamic contexts.
