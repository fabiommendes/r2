/**
 * Demo page for the e2e suite: converts whatever is typed in either direction.
 */

import { fromRoman, RomanError, toRoman } from "./roman";

const input = document.querySelector<HTMLInputElement>("#input")!;
const output = document.querySelector<HTMLOutputElement>("#output")!;
const button = document.querySelector<HTMLButtonElement>("#convert")!;

function convert(text: string): string {
  const trimmed = text.trim();
  if (/^-?\d+$/.test(trimmed)) {
    return toRoman(Number(trimmed));
  }
  return String(fromRoman(trimmed.toUpperCase()));
}

button.addEventListener("click", () => {
  try {
    output.textContent = convert(input.value);
    output.className = "ok";
  } catch (error) {
    if (!(error instanceof RomanError)) throw error;
    output.textContent = error.message;
    output.className = "error";
  }
});
