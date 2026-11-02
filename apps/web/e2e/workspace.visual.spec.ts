import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const password = process.env.KEYCLOAK_USER_A_PASSWORD;
const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

async function authenticate(page: Page) {
  await page.goto(`${apiURL}/auth/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#username").fill("pmc-user-a");
  await page.locator("#password").fill(String(password));
  await page.locator("#kc-login").click();
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:(3000|8000)\//);
  await page.goto("/", { waitUntil: "networkidle" });
  const organization = page.getByRole("combobox", { name: "Current organization" });
  if (await organization.isVisible()) {
    const values = await organization.locator("option:not([disabled])").evaluateAll((options) =>
      options.map((option) => (option as HTMLOptionElement).value).filter(Boolean),
    );
    if (values[0]) {
      await organization.selectOption(values[0]);
      await page.waitForLoadState("networkidle");
    }
  }
  await expect(page.getByRole("heading", { name: "Work with clarity." })).toBeVisible();
}

for (const viewport of [
  { name: "mobile", width: 375, height: 812 },
  { name: "desktop", width: 1280, height: 900 },
] as const) {
  test(`authenticated workspace ${viewport.name}`, async ({ page }) => {
    test.skip(!password, "Local development credential was not provided");
    await page.setViewportSize(viewport);
    await authenticate(page);
    await page.evaluate(() => document.fonts.ready);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await expect(page).toHaveScreenshot(`workspace-${viewport.name}.png`, {
      fullPage: true,
    });
  });
}
