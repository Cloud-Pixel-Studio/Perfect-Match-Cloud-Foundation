import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

const password = process.env.KEYCLOAK_USER_A_PASSWORD;
const apiURL = process.env.PLAYWRIGHT_API_URL ?? "http://127.0.0.1:8000";

async function authenticate(page: Page) {
  await page.goto(`${apiURL}/auth/login`, { waitUntil: "domcontentloaded" });
  await page.locator("#username").fill("pmc-user-a");
  await page.locator("#password").fill(String(password));
  await page.locator("#kc-login").click();
  await page.waitForURL(/^http:\/\/127\.0\.0\.1:(3000|8000)\//);
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByRole("heading", { name: "Work with clarity." })).toBeVisible();
}

const modules = [
  { hash: "process-title", heading: "process-title", name: "processes" },
  { hash: "documents-heading", heading: "documents-heading", name: "documents" },
  { hash: "controls-heading", heading: "controls-heading", name: "controls" },
  { hash: "risks-heading", heading: "risks-heading", name: "risks" },
  { hash: "ncr-heading", heading: "ncr-heading", name: "nonconformities" },
  { hash: "capa-heading", heading: "capa-heading", name: "corrective-actions" },
] as const;

async function inspectModule(page: Page, testInfo: TestInfo, item: (typeof modules)[number], viewport: string) {
  await page.goto(`/#${item.hash}`, { waitUntil: "networkidle" });
  await expect(page.locator(`#${item.heading}`)).toBeVisible();

  const unit = page.locator("#qms-active-workspace select").first();
  if (await unit.isVisible()) {
    const option = unit.locator('option:not([disabled])[value]:not([value=""])').first();
    if (await option.count()) {
      await unit.selectOption(String(await option.getAttribute("value")));
      await page.waitForLoadState("networkidle");
    }
  }
  const skeleton = page.locator("#qms-active-workspace > section > .record-skeleton");
  if (await skeleton.count()) await expect(skeleton).toBeHidden({ timeout: 10_000 });
  await page.evaluate(() => document.fonts.ready);

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
  const accessibility = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await testInfo.attach(`${item.name}-${viewport}`, {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
}

for (const viewport of [
  { name: "mobile", width: 375, height: 812 },
  { name: "desktop", width: 1440, height: 1000 },
] as const) {
  test(`operational modules ${viewport.name} experience`, async ({ page }, testInfo) => {
    test.skip(!password, "Local development credential was not provided");
    await page.setViewportSize(viewport);
    await authenticate(page);
    for (const item of modules) await inspectModule(page, testInfo, item, viewport.name);
  });
}
