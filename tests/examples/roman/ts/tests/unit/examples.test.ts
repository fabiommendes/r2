// Example-based tests. See tests/examples/roman/README.md for the role of
// each test in the baseline.

import { expect, test } from "vitest";
import { fromRoman, toRoman } from "../../src/roman";

const KNOWN_VALUES: [number, string][] = [
  [1, "I"],
  [4, "IV"],
  [9, "IX"],
  [14, "XIV"],
  [40, "XL"],
  [90, "XC"],
  [400, "CD"],
  [900, "CM"],
  [1994, "MCMXCIV"],
  [3999, "MMMCMXCIX"],
];

test("toRoman known values", () => {
  for (const [n, numeral] of KNOWN_VALUES) {
    expect(toRoman(n)).toBe(numeral);
  }
});

test("toRoman returns string", () => {
  expect(typeof toRoman(5)).toBe("string");
});

test("fromRoman IV", () => {
  expect(fromRoman("IV")).toBe(4);
});

test("roundtrip small", () => {
  for (let n = 1; n <= 10; n++) {
    expect(fromRoman(toRoman(n))).toBe(n);
  }
});

test("toRoman rejects zero", () => {
  expect(() => toRoman(0)).toThrow();
});

test("toRoman rejects 4000", () => {
  expect(() => toRoman(4000)).toThrow();
});

test("fromRoman rejects empty", () => {
  expect(() => fromRoman("")).toThrow();
});

test("fromRoman rejects invalid symbol", () => {
  expect(() => fromRoman("ABC")).toThrow();
});

test("fromRoman rejects out of range", () => {
  expect(() => fromRoman("MMMM")).toThrow();
});

test("fromRoman rejects non canonical", () => {
  for (const numeral of ["IIII", "IC", "VX"]) {
    expect(() => fromRoman(numeral)).toThrow();
  }
});
