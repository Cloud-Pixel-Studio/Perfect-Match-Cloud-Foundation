import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { authenticateWithKeycloak } from "./support/auth";

const password = process.env.KEYCLOAK_OWNER_PASSWORD;

async function authenticateOwner(page: Page) {
  await authenticateWithKeycloak(page, {
    username: "pmc-local-owner",
    password: String(password),
    destination: "/#audit-heading",
  });
  await expect(page.getByRole("heading", { name: "Audit trail" })).toBeVisible();
}

for (const viewport of [
  { name: "mobile", width: 375, height: 812 },
  { name: "desktop", width: 1440, height: 1000 },
] as const) {
  test(`administration audit workspace ${viewport.name}`, async ({ page }, testInfo) => {
    test.skip(!password, "Local owner development credential was not provided");
    await page.setViewportSize(viewport);
    await authenticateOwner(page);
    const skeleton = page.locator(".audit-panel .record-skeleton");
    if (await skeleton.count()) await expect(skeleton).toBeHidden({ timeout: 10_000 });
    await expect(page.getByRole("form", { name: "Filter audit history" })).toBeVisible();

    const firstEvent = page.locator(".audit-event").first();
    if (await firstEvent.count()) await firstEvent.locator("summary").click();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "auto" }));
    const screenshot = testInfo.outputPath(`audit-workspace-${viewport.name}.png`);
    await page.screenshot({ fullPage: true, path: screenshot });
    await testInfo.attach(`audit-workspace-${viewport.name}`, { path: screenshot, contentType: "image/png" });

    if (viewport.name === "desktop") {
      const actionFilter = page.getByRole("form", { name: "Filter audit history" }).getByLabel("Action", { exact: true });
      const options = actionFilter.locator("option");
      if (await options.count() > 1) {
        const expectedLabel = await options.nth(1).textContent();
        await actionFilter.selectOption({ index: 1 });
        await expect(page.locator(".audit-panel")).toHaveAttribute("aria-busy", "false");
        await expect(page.locator(".audit-event-title strong").first()).toHaveText(String(expectedLabel));
        await actionFilter.selectOption("");
        await expect(page.locator(".audit-panel")).toHaveAttribute("aria-busy", "false");
      }

      const loadOlder = page.getByRole("button", { name: "Load older events" });
      if (await loadOlder.isVisible()) {
        const initialCount = await page.locator(".audit-event").count();
        await loadOlder.click();
        await expect(page.locator(".audit-panel")).toHaveAttribute("aria-busy", "false");
        expect(await page.locator(".audit-event").count()).toBeGreaterThan(initialCount);
      }
    }
  });
}

test("audit refresh clears stale evidence when the service fails", async ({ page }) => {
  test.skip(!password, "Local owner development credential was not provided");
  await authenticateOwner(page);
  await expect(page.locator(".audit-panel")).toHaveAttribute("aria-busy", "false");
  expect(await page.locator(".audit-event").count()).toBeGreaterThan(0);
  await page.route("**/api/identity/audit/events?**", async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Unavailable" }) });
  });
  await page.getByRole("button", { name: "Refresh history" }).click();
  await expect(page.locator(".audit-panel .denied-state")).toContainText("temporarily unavailable");
  await expect(page.locator(".audit-event")).toHaveCount(0);
});
