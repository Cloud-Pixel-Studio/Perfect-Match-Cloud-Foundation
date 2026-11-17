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
    await page.locator(".studio-gallery img").evaluateAll((images) =>
      Promise.all(images.map((image) => (image as HTMLImageElement).decode())),
    );
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

    await page.getByRole("checkbox", { name: "Use dark theme" }).check({ force: true });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const darkAccessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(darkAccessibility.violations).toEqual([]);
    await expect(page).toHaveScreenshot(`design-studio-${viewport.name}-dark.png`, {
      fullPage: true,
    });
  });
}

test("visual library preserves the chosen theme and downloads a real PNG", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/products", { waitUntil: "networkidle" });
  await page.getByRole("checkbox", { name: "Use dark theme" }).check({ force: true });
  await page.getByRole("link", { name: "Explore the visual library" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(".studio-download")).toHaveCount(6);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download PNG: Banner principal", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("platform-hero.png");
  expect(await download.failure()).toBeNull();
});
