import { test, expect } from "@playwright/test";

const PV_NAME = process.env.TEST_PV;

test.skip(
  !PV_NAME,
  "Set TEST_PV to run the live PV test"
);

test("receives a live PV value", async ({ page }) => {
  // Register diagnostic listeners before loading the application.
  page.on("console", (message) => {
    console.log(
      `[BROWSER ${message.type()}] ${message.text()}`
    );
  });

  page.on("pageerror", (error) => {
    console.error(
      `[BROWSER PAGE ERROR] ${error.message}`
    );
  });

  page.on("requestfailed", (request) => {
    console.error(
      `[REQUEST FAILED] ${request.url()} ` +
        `${request.failure()?.errorText ?? ""}`
    );
  });

  page.on("websocket", (webSocket) => {
    console.log(
      `[WEBSOCKET OPENED] ${webSocket.url()}`
    );

    webSocket.on("framereceived", (event) => {
      console.log(
        `[WEBSOCKET FRAME RECEIVED] ${event.payload}`
      );
    });

    webSocket.on("framesent", (event) => {
      console.log(
        `[WEBSOCKET FRAME SENT] ${event.payload}`
      );
    });

    webSocket.on("socketerror", (error) => {
      console.error(
        `[WEBSOCKET ERROR] ${error}`
      );
    });

    webSocket.on("close", () => {
      console.log(
        `[WEBSOCKET CLOSED] ${webSocket.url()}`
      );
    });
  });

  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.goto("/");

  const webSocketPromise = page.waitForEvent(
    "websocket",
    {
      timeout: 10_000,
    }
  );

  await page
    .getByPlaceholder(/Enter PV name/i)
    .fill(PV_NAME);

  await page
    .getByRole("button", {
      name: /Add Plot/i,
    })
    .click();

  const webSocket = await webSocketPromise;

  console.log(
    `[TEST] WebSocket URL: ${webSocket.url()}`
  );

  expect(webSocket.url()).toContain("/ws?pv=");

  const valueItem = page
    .locator(".value-item")
    .filter({ hasText: PV_NAME });

  await expect(valueItem).toBeVisible();

  const valueElement = valueItem.locator(".pv-value");

  await expect(valueElement).not.toHaveText("---", {
    timeout: 20_000,
  });

  console.log(
    `[TEST] Displayed value: ` +
      `${await valueElement.textContent()}`
  );
});
