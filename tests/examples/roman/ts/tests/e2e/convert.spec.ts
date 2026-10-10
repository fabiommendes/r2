// End-to-end tests through the demo page. See tests/examples/roman/README.md.

import { expect, test } from "@playwright/test";

async function convert(page: import("@playwright/test").Page, text: string) {
  await page.goto("/");
  await page.fill("#input", text);
  await page.click("#convert");
  return page.locator("#output");
}

test("converts a number to a numeral", async ({ page }) => {
  await expect(await convert(page, "1994")).toHaveText("MCMXCIV");
});

test("converts a numeral to a number", async ({ page }) => {
  await expect(await convert(page, "mcmxciv")).toHaveText("1994");
});

test("shows an error for invalid input", async ({ page }) => {
  const output = await convert(page, "0");
  await expect(output).toHaveClass("error");
});
