// Core suite: property-based tests. See tests/examples/roman/README.md.

import fc from "fast-check";
import { expect, test } from "vitest";
import { fromRoman, MAX_VALUE, MIN_VALUE, toRoman } from "../../src/roman";

const numbers = fc.integer({ min: MIN_VALUE, max: MAX_VALUE });
const params = { seed: 0 };

test("roundtrip", () => {
  fc.assert(
    fc.property(numbers, (n) => {
      expect(fromRoman(toRoman(n))).toBe(n);
    }),
    params,
  );
});

test("toRoman uses only roman symbols", () => {
  fc.assert(
    fc.property(numbers, (n) => {
      expect(toRoman(n)).toMatch(/^[IVXLCDM]+$/);
    }),
    params,
  );
});
