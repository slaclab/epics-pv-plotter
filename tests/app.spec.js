import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.goto("/");
});

test("loads the PV plotter", async ({ page }) => {
  await expect(
    page.getByPlaceholder(/Enter PV name/i)
  ).toBeVisible();

  await expect(
    page.getByRole("button", {
      name: /Add Plot/i,
    })
  ).toBeVisible();

  await expect(
    page.getByRole("button", {
      name: /Clear All/i,
    })
  ).toBeVisible();

  await expect(
    page.getByText("No plots yet")
  ).toBeVisible();
});

test("adds a single PV plot", async ({ page }) => {
  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill("TEST:PV:01");

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  await expect(
    page.locator(".plot-widget")
  ).toHaveCount(1);

  await expect(
    page.locator(".right-sidebar")
  ).toContainText("TEST:PV:01");
});

test("adds multiple PVs to one plot", async ({ page }) => {
  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill("TEST:PV:01,TEST:PV:02");

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  await expect(
    page.locator(".plot-widget")
  ).toHaveCount(1);

  const sidebar = page.locator(".right-sidebar");

  await expect(sidebar).toContainText("TEST:PV:01");
  await expect(sidebar).toContainText("TEST:PV:02");
});

test("clears all plots", async ({ page }) => {
  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill("TEST:PV:01");

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  await expect(
    page.locator(".plot-widget")
  ).toHaveCount(1);

  page.once("dialog", async (dialog) => {
    expect(dialog.type()).toBe("confirm");
    await dialog.accept();
  });

  await page
    .getByRole("button", {
      name: /Clear All/i,
    })
    .click();

  await expect(
    page.locator(".plot-widget")
  ).toHaveCount(0);

  await expect(
    page.getByText("No plots yet")
  ).toBeVisible();
});
