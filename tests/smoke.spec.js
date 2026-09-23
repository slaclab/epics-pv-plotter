import { test, expect } from "@playwright/test";

test("Playwright can launch Chromium", async ({ page }) => {
  await page.goto(
    "data:text/html,<h1>Playwright Works</h1>"
  );

  await expect(
    page.getByRole("heading", {
      name: "Playwright Works",
    })
  ).toBeVisible();
});
