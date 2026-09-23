import { test, expect } from "@playwright/test";

const PV_NAME = process.env.TEST_PV;

test.skip(
  !PV_NAME,
  "Set TEST_PV to run the live PV test"
);

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.goto("/");
});

test("receives a live PV value", async ({ page }) => {
  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill(PV_NAME);

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  const valueItem = page
    .locator(".value-item")
    .filter({ hasText: PV_NAME });

  await expect(valueItem).toBeVisible();

  await expect(
    valueItem.locator(".pv-value")
  ).not.toHaveText("---", {
    timeout: 20_000,
  });
});
