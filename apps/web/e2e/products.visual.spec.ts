import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const viewports = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "desktop", width: 1280, height: 900 },
] as const;

for (const viewport of viewports) {
  test(`product catalog ${viewport.name} visual and accessibility`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/products", { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);

    await expect(
      page.getByRole("heading", { name: "Your QMS foundation. Standards added by edition." }),
    ).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await expect(page).toHaveScreenshot(`products-${viewport.name}.png`, {
      fullPage: true,
    });
  });
}

test("product catalog dark theme and keyboard focus", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/products", { waitUntil: "networkidle" });
  await page.getByRole("checkbox", { name: "Use dark theme" }).check({ force: true });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus-visible")).toBeVisible();
  await expect(page).toHaveScreenshot("products-desktop-dark.png", {
    fullPage: true,
  });
});
