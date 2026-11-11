import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const viewport of [
  { name: "mobile", width: 375, height: 812 },
  { name: "desktop", width: 1440, height: 1100 },
] as const) {
  test(`design studio ${viewport.name} visual and accessibility`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/design-studio", { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.fonts.ready);

    await expect(page.getByRole("heading", { name: "AI Design Studio" })).toBeVisible();
    await expect(page.locator(".studio-gallery figure")).toHaveCount(6);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      ),
    ).toBeLessThanOrEqual(1);

    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await expect(page).toHaveScreenshot(`design-studio-${viewport.name}.png`, {
      fullPage: true,
    });
  });
}
