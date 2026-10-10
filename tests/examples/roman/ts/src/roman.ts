/**
 * Convert integers in 1..3999 to Roman numerals and back.
 */

export const MIN_VALUE = 1;
export const MAX_VALUE = 3999;

const NUMERALS: [number, string][] = [
  [1000, "M"],
  [900, "CM"],
  [500, "D"],
  [400, "CD"],
  [100, "C"],
  [90, "XC"],
  [50, "L"],
  [40, "XL"],
  [10, "X"],
  [9, "IX"],
  [5, "V"],
  [4, "IV"],
  [1, "I"],
];

const VALUES: Record<string, number> = {
  I: 1,
  V: 5,
  X: 10,
  L: 50,
  C: 100,
  D: 500,
  M: 1000,
};

export class RomanError extends Error {}

export function toRoman(n: number): string {
  if (!Number.isInteger(n) || n < MIN_VALUE || n > MAX_VALUE) {
    throw new RomanError(`${n} is out of range ${MIN_VALUE}..${MAX_VALUE}`);
  }

  let out = "";
  for (const [value, symbol] of NUMERALS) {
    out += symbol.repeat(Math.floor(n / value));
    n %= value;
  }
  return out;
}

export function fromRoman(s: string): number {
  if (s === "") {
    throw new RomanError("empty numeral");
  }

  let total = 0;
  for (let i = 0; i < s.length; i++) {
    const value = VALUES[s[i]];
    if (value === undefined) {
      throw new RomanError(`invalid symbol ${JSON.stringify(s[i])}`);
    }
    const next = i + 1 < s.length ? (VALUES[s[i + 1]] ?? 0) : 0;
    if (next > value) {
      total -= value;
    } else {
      total += value;
    }
  }

  if (total < MIN_VALUE || total > MAX_VALUE) {
    throw new RomanError(`${JSON.stringify(s)} is out of range ${MIN_VALUE}..${MAX_VALUE}`);
  }
  if (toRoman(total) !== s) {
    throw new RomanError(`${JSON.stringify(s)} is not in canonical form`);
  }
  return total;
}
