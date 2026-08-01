import { expect, test } from "@playwright/test";

/**
 * Browser e2e against local stack.
 * Requires: API :8000 + demo UI :5173 (./scripts/start-*.sh)
 * Skip automatically when UI is down.
 */
test.describe("demo UI smoke", () => {
  test.beforeEach(async ({ request }, testInfo) => {
    try {
      const res = await request.get("http://localhost:5173/", { timeout: 2000 });
      if (!res.ok()) testInfo.skip(true, "demo UI not running on :5173");
    } catch {
      testInfo.skip(true, "demo UI not running on :5173");
    }
  });

  test("loads cases dashboard", async ({ page }) => {
    await page.goto("http://localhost:5173/");
    await expect(page.getByRole("heading", { name: /Investigation cases/i })).toBeVisible({
      timeout: 15000,
    });
  });

  test("navigates to new investigation", async ({ page }) => {
    await page.goto("http://localhost:5173/");
    await page.getByRole("link", { name: /New/i }).first().click();
    await expect(page.getByText(/New investigation|Create|Upload|vertical/i).first()).toBeVisible({
      timeout: 10000,
    });
  });
});
