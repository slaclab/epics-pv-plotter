import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",

  fullyParallel: false,
  workers: 1,

  timeout: 30_000,

  expect: {
    timeout: 10_000,
  },

  reporter: [
    ["list"],
    ["html", { open: "never" }],
  ],

  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },


  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: false,
    timeout: 120_000,
  
    env: {
      ...process.env,
      VITE_WS_BASE_URL: "ws://127.0.0.1:8000",
    },
  },


  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],

        // The EPICS WebSocket gateway is on the local network.
        // Do not route WebSocket traffic through the system proxy.
        launchOptions: {
          args: [
            "--no-proxy-server",
          ],
        },
      },
    },
  ],
});
