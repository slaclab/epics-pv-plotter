# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: live-pv.spec.js >> receives a live PV value
- Location: tests/live-pv.spec.js:10:1

# Error details

```
Error: expect(locator).not.toHaveText(expected) failed

Locator:  locator('.value-item').filter({ hasText: 'BL22:SCAN:MASTER:ADC1' }).locator('.pv-value')
Expected: not "---"
Received: "---"

Call log:
  - Expect "not toHaveText" locator('.value-item').filter({ hasText: 'BL22:SCAN:MASTER:ADC1' }).locator('.pv-value') with timeout 20000ms
  - waiting for locator('.value-item').filter({ hasText: 'BL22:SCAN:MASTER:ADC1' }).locator('.pv-value')
    15 × locator resolved to <div class="pv-value">---</div>
       - unexpected value "---"
  - Test ended.

```

```yaml
- text: "---"
```

# Test source

```ts
  1   | import { test, expect } from "@playwright/test";
  2   | 
  3   | const PV_NAME = process.env.TEST_PV;
  4   | 
  5   | test.skip(
  6   |   !PV_NAME,
  7   |   "Set TEST_PV to run the live PV test"
  8   | );
  9   | 
  10  | test("receives a live PV value", async ({ page }) => {
  11  |   // Register diagnostic listeners before loading the application.
  12  |   page.on("console", (message) => {
  13  |     console.log(
  14  |       `[BROWSER ${message.type()}] ${message.text()}`
  15  |     );
  16  |   });
  17  | 
  18  |   page.on("pageerror", (error) => {
  19  |     console.error(
  20  |       `[BROWSER PAGE ERROR] ${error.message}`
  21  |     );
  22  |   });
  23  | 
  24  |   page.on("requestfailed", (request) => {
  25  |     console.error(
  26  |       `[REQUEST FAILED] ${request.url()} ` +
  27  |         `${request.failure()?.errorText ?? ""}`
  28  |     );
  29  |   });
  30  | 
  31  |   page.on("websocket", (webSocket) => {
  32  |     console.log(
  33  |       `[WEBSOCKET OPENED] ${webSocket.url()}`
  34  |     );
  35  | 
  36  |     webSocket.on("framereceived", (event) => {
  37  |       console.log(
  38  |         `[WEBSOCKET FRAME RECEIVED] ${event.payload}`
  39  |       );
  40  |     });
  41  | 
  42  |     webSocket.on("framesent", (event) => {
  43  |       console.log(
  44  |         `[WEBSOCKET FRAME SENT] ${event.payload}`
  45  |       );
  46  |     });
  47  | 
  48  |     webSocket.on("socketerror", (error) => {
  49  |       console.error(
  50  |         `[WEBSOCKET ERROR] ${error}`
  51  |       );
  52  |     });
  53  | 
  54  |     webSocket.on("close", () => {
  55  |       console.log(
  56  |         `[WEBSOCKET CLOSED] ${webSocket.url()}`
  57  |       );
  58  |     });
  59  |   });
  60  | 
  61  |   await page.addInitScript(() => {
  62  |     localStorage.clear();
  63  |   });
  64  | 
  65  |   await page.goto("/");
  66  | 
  67  |   const webSocketPromise = page.waitForEvent(
  68  |     "websocket",
  69  |     {
  70  |       timeout: 10_000,
  71  |     }
  72  |   );
  73  | 
  74  |   await page
  75  |     .getByPlaceholder(/Enter PV name/i)
  76  |     .fill(PV_NAME);
  77  | 
  78  |   await page
  79  |     .getByRole("button", {
  80  |       name: /Add Plot/i,
  81  |     })
  82  |     .click();
  83  | 
  84  |   const webSocket = await webSocketPromise;
  85  | 
  86  |   console.log(
  87  |     `[TEST] WebSocket URL: ${webSocket.url()}`
  88  |   );
  89  | 
  90  |   expect(webSocket.url()).toContain("/ws?pv=");
  91  | 
  92  |   const valueItem = page
  93  |     .locator(".value-item")
  94  |     .filter({ hasText: PV_NAME });
  95  | 
  96  |   await expect(valueItem).toBeVisible();
  97  | 
  98  |   const valueElement = valueItem.locator(".pv-value");
  99  | 
> 100 |   await expect(valueElement).not.toHaveText("---", {
      |                                  ^ Error: expect(locator).not.toHaveText(expected) failed
  101 |     timeout: 20_000,
  102 |   });
  103 | 
  104 |   console.log(
  105 |     `[TEST] Displayed value: ` +
  106 |       `${await valueElement.textContent()}`
  107 |   );
  108 | });
  109 | 
```