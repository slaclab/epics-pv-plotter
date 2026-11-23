import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.route("**/api/config/events**", (route) => route.abort());
  await page.route("**/api/config-presets", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({ files: ["config.json"] }),
    }),
  );
  await page.route("**/api/config-presets/config.json", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "*" },
      body: JSON.stringify({
        layouts: {
          default: {
            plots: [],
            livePVNames: [],
            globalTimeWindow: 60,
            showBeamlineStatus: false,
          },
        },
        aliases: { "BL22:GAS.IC2P": "IC2 Gas Pressure" },
        egus: {},
        thresholds: {},
        value_formats: {},
      }),
    }),
  );

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

  await expect(
    page.getByRole("button", {
      name: /Load Standard Configuration/i,
    })
  ).toBeVisible();

  await expect(
    page.getByRole("combobox", {
      name: /Configuration preset/i,
    })
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

  await expect(
    page.getByRole("button", {
      name: /Load Standard Configuration/i,
    })
  ).toHaveCount(0);

  await expect(
    page.getByRole("combobox", {
      name: /Configuration preset/i,
    })
  ).toHaveCount(0);
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

test("edits the PVs in a multi-PV plot", async ({ page }) => {
  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill("TEST:PV:01,TEST:PV:02");

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  await page
    .getByRole("button", {
      name: /Edit PVs in this plot/i,
    })
    .click();

  const dialog = page.getByRole("dialog", {
    name: /Edit PVs in this plot/i,
  });
  await expect(dialog).toBeVisible();

  await dialog
    .getByRole("button", {
      name: "Remove TEST:PV:02",
    })
    .click();

  await dialog
    .getByLabel("New PV name")
    .fill("TEST:PV:03");
  await dialog
    .getByRole("button", {
      name: "Add PV",
    })
    .click();

  await dialog
    .getByRole("button", {
      name: "Confirm",
    })
    .click();

  await expect(dialog).toHaveCount(0);

  const sidebar = page.locator(".right-sidebar");
  await expect(sidebar).toContainText("TEST:PV:01");
  await expect(sidebar).not.toContainText("TEST:PV:02");
  await expect(sidebar).toContainText("TEST:PV:03");
});

test("shows the matching gas pressure PV for an ion chamber ADC", async ({ page }) => {
  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill("BL22:SCAN:MASTER:ADC2");

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  const adcPanel = page
    .locator(".value-item")
    .filter({ hasText: "BL22:SCAN:MASTER:ADC2" });

  await expect(adcPanel).toContainText("Gas Pressure");
  await expect(adcPanel).toContainText("IC2 Gas Pressure");

  await page
    .locator(".sidebar-alias-toggle")
    .filter({ hasText: "Show PV Names" })
    .click();
  await expect(adcPanel).toContainText("BL22:GAS.IC2P");

  await page
    .getByRole("button", {
      name: /PV Configurations/i,
    })
    .click();

  const gasPressureRow = page
    .locator("tr")
    .filter({ hasText: "BL22:GAS.IC2P" });
  await expect(gasPressureRow).toBeVisible();
  await expect(gasPressureRow.getByPlaceholder("(no alias)")).toBeVisible();
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
