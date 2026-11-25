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
  await page.route("**/api/spear-messages", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ messages: [], TIME: "23-Nov-2026 15:32:43" }),
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

test("shows and wraps SPEAR operator messages below the beamline status table", async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 800 });
  await page.route(/\/api\/spear-messages/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        TIME: "23-Nov-2026 15:32:43",
        messages: [
          {
            activationDate: "Nov 23, 2026",
            message:
              "Beam current stable while operators prepare the next injection cycle; please monitor beamline conditions before proceeding.",
          },
        ],
      }),
    }),
  );

  await page.getByRole("button", { name: "Show", exact: true }).click();

  const message = page.locator(".beamline-spear-messages");
  await expect(message).toContainText("TIME:");
  await expect(message).toContainText("23-Nov-2026 15:32:43");
  await expect(message).toContainText("Nov 23, 2026");
  await expect(message).toContainText(
    "Beam current stable while operators prepare the next injection cycle; please monitor beamline conditions before proceeding.",
  );
  await expect(
    page.locator(".beamline-spear-message-row td"),
  ).toHaveCSS("overflow-wrap", "anywhere");
  await expect(
    page.locator(".beamline-spear-current-time time"),
  ).toHaveCSS("color", "rgb(255, 87, 51)");
  await expect(
    page.locator(".beamline-spear-message time"),
  ).toHaveCSS("color", "rgb(255, 87, 51)");
  await expect(
    page.locator(".beamline-spear-time-label"),
  ).toHaveCSS("font-size", "16px");
  await expect(
    page.locator(".beamline-spear-current-time"),
  ).toHaveCSS("align-items", "baseline");

  await expect(
    page.locator(".beamline-status-table tr").last(),
  ).toContainText("Beam current stable");
});

test("hides the SPEAR row when there are no messages", async ({ page }) => {
  await page.getByRole("button", { name: "Show", exact: true }).click();
  await expect(page.locator(".beamline-spear-message-row")).toHaveCount(0);
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

test("saves an empty layout as a new preset without patching the source", async ({ page }) => {
  const saveRequests = [];
  page.on("request", (request) => {
    if (
      request.url().includes("/api/config-presets/") &&
      ["POST", "PATCH"].includes(request.method())
    ) {
      saveRequests.push(request);
    }
  });
  await page.route(/\/api\/config-presets\/config4\.json/, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", filename: "config4.json" }),
    }),
  );

  await page.getByLabel("New configuration filename").fill("config4.json");
  await page.getByRole("button", { name: "Save As" }).click();

  await expect(page.getByLabel("New configuration filename")).toHaveValue("");
  expect(saveRequests).toHaveLength(1);
  expect(saveRequests[0].method()).toBe("POST");
  expect(new URL(saveRequests[0].url()).searchParams.get("source")).toBe(
    "config.json",
  );
  expect(JSON.parse(saveRequests[0].postData()).layouts.default.plots).toEqual(
    [],
  );
});
