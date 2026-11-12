import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { chromium } from "@playwright/test";

const assets = [
  ["platform-hero", 1600, 900],
  ["saas-product-overview", 1600, 900],
  ["dashboard-mockup", 1600, 1000],
  ["quality-linkedin", 1200, 1200],
  ["audit-readiness", 1200, 628],
  ["qms-capabilities", 1200, 1200],
];

const baseUrl = new URL(process.env.DESIGN_STUDIO_BASE_URL ?? "http://127.0.0.1:3100");
if (baseUrl.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(baseUrl.hostname)) {
  throw new Error("Design asset rendering is restricted to a loopback HTTP server.");
}

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const outputDirectory = path.resolve(scriptDirectory, "../public/brand/design-studio/demo");
await mkdir(outputDirectory, { recursive: true });

const browser = await chromium.launch({ headless: true });
try {
  for (const [slug, width, height] of assets) {
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
    const url = new URL("/design-studio", baseUrl);
    url.searchParams.set("asset", slug);
    await page.goto(url.toString(), { waitUntil: "domcontentloaded" });
    await page.locator(`[data-export-asset="${slug}"]`).waitFor();
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        Array.from(document.images, (image) =>
          image.complete
            ? Promise.resolve()
            : new Promise((resolve) => {
                image.addEventListener("load", resolve, { once: true });
                image.addEventListener("error", resolve, { once: true });
              }),
        ),
      );
    });
    await page.locator(`[data-export-asset="${slug}"]`).screenshot({
      animations: "disabled",
      path: path.join(outputDirectory, `${slug}.png`),
    });
    await page.close();
  }
} finally {
  await browser.close();
}

console.log(`Rendered ${assets.length} controlled design assets to ${outputDirectory}`);
