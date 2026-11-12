import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium, expect } from "@playwright/test";

const baseURL = new URL(process.env.PRODUCT_CAPTURE_BASE_URL ?? "http://127.0.0.1:3000");
if (baseURL.origin !== "http://127.0.0.1:3000" || baseURL.pathname !== "/") {
  throw new Error("Product capture is restricted to the local SaaS origin on port3000.");
}
const password = process.env.KEYCLOAK_USER_A_PASSWORD;
if (!password) throw new Error("The existing synthetic development credential is required.");

const apiURL = "http://127.0.0.1:8000";
const identityOrigin = "http://127.0.0.1:8080";
const allowedOrigins = new Set([baseURL.origin, apiURL, identityOrigin]);
const outputDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../public/brand/product");
const viewport = { width: 1440, height: 1000 };
const views = [
  { slug: "overview", hash: "overview-heading", heading: "Work with clarity. Improve with evidence." },
  { slug: "documents", hash: "documents-heading", heading: "Document control", code: "DEMO-DOC-001", register: ".document-list", detail: ".document-detail .detail-heading .eyebrow" },
  { slug: "risks", hash: "risks-heading", heading: "Risks & opportunities", code: "DEMO-RSK-001", register: ".risk-register-grid > aside", detail: ".risk-detail .eyebrow" },
  { slug: "capa", hash: "capa-heading", heading: "Corrective actions", code: "DEMO-CAPA-001", register: ".ncr-record-list", detail: ".ncr-detail .ncr-detail-heading .eyebrow" },
];

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, colorScheme: "light", reducedMotion: "reduce", locale: "en-US", timezoneId: "America/New_York" });
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!allowedOrigins.has(url.origin)) return route.abort();
    if (!["GET", "HEAD"].includes(request.method())) {
      const loginSubmission = url.origin === identityOrigin && url.pathname.startsWith("/realms/perfect-match/login-actions/");
      const tenantSelection = url.origin === baseURL.origin && url.pathname === "/api/identity/auth/tenant";
      if (!loginSubmission && !tenantSelection) return route.abort();
    }
    return route.continue();
  });

  const page = await context.newPage();
  const response = await page.goto(`${apiURL}/auth/login`, { waitUntil: "domcontentloaded" });
  if (!response?.ok() || new URL(page.url()).origin !== identityOrigin) throw new Error("Local identity login was unavailable.");
  await page.locator("#username").fill("pmc-user-a");
  await page.locator("#password").fill(password);
  await Promise.all([
    page.waitForURL((url) => url.origin === baseURL.origin && url.pathname === "/", { waitUntil: "networkidle", timeout: 20_000 }),
    page.locator("#kc-login").click(),
  ]);
  await expect(page.locator(".user-menu strong")).toHaveText("pmc-user-a Synthetic");
  const organization = page.getByRole("combobox", { name: "Current organization" });
  await organization.selectOption({ label: "Tenant A · member" });
  await expect(page.locator(".qms-sidebar-intro small")).toHaveText("Tenant A");
  await expect(organization).toBeEnabled();

  const assets = [];
  for (const view of views) {
    await page.goto(`${baseURL.origin}/#${view.hash}`, { waitUntil: "networkidle" });
    await expect(page.locator(".user-menu strong")).toHaveText("pmc-user-a Synthetic");
    await expect(page.locator(".qms-sidebar-intro small")).toHaveText("Tenant A");
    const panel = page.locator("#qms-active-workspace");
    const heading = page.getByRole("heading", { name: view.heading, exact: true });
    await expect(heading).toBeVisible();

    if (view.code) {
      const unit = panel.locator("select").first();
      const unitOption = unit.locator("option").filter({ hasText: "DEV-ACCESS-UI" });
      await expect(unitOption).toHaveCount(1);
      await unit.selectOption(String(await unitOption.getAttribute("value")));
      await page.waitForLoadState("networkidle");
      await panel.getByRole("textbox", { name: /^Find by code or (title|name)$/ }).fill(view.code);
      await panel.getByRole("button", { name: /^Search( risks)?$/ }).click();
      await page.waitForLoadState("networkidle");
      const record = panel.locator(view.register).getByRole("button").filter({ hasText: view.code });
      await expect(record).toHaveCount(1);
      await record.click();
      await page.waitForLoadState("networkidle");
      await expect(panel.locator(view.detail).first()).toContainText(view.code);
    }
    await expect(panel.getByRole("alert")).toHaveCount(0);
    await expect(panel.locator(".record-skeleton")).toHaveCount(0);
    await page.evaluate(() => document.fonts.ready);
    await heading.click();
    await page.evaluate(async () => {
      window.scrollTo({ top: 0, left: 0, behavior: "instant" });
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    });

    const outputPath = path.join(outputDirectory, `${view.slug}.png`);
    let crop = null;
    if (view.code) {
      const box = await panel.boundingBox();
      if (!box || box.x < 0 || box.y < 0) throw new Error(`The ${view.slug} panel was not available for capture.`);
      crop = { x: Math.floor(box.x), y: Math.floor(box.y), width: Math.floor(box.width), height: Math.min(800, Math.floor(box.height), viewport.height - Math.ceil(box.y)) };
      await page.screenshot({ path: outputPath, clip: crop, animations: "disabled" });
    } else {
      await page.screenshot({ path: outputPath, fullPage: false, animations: "disabled" });
    }
    const file = await readFile(outputPath);
    assets.push({ path: `${view.slug}.png`, width: file.readUInt32BE(16), height: file.readUInt32BE(20), sha256: createHash("sha256").update(file).digest("hex"), sourceURL: `${baseURL.origin}/#${view.hash}`, selectedRecordCode: view.code ?? null, crop, disclosure: "Real local Perfect Match QMS interface with synthetic demonstration data." });
  }
  await writeFile(path.join(outputDirectory, "asset-manifest.json"), `${JSON.stringify({ schemaVersion: 1, capturedAt: new Date().toISOString(), source: "Existing local SaaS runtime; isolated Playwright browser; pmc-user-a Synthetic; Tenant A", classification: "synthetic-demo-only", viewport, deviceScaleFactor: 1, browserPlatform: process.platform, policy: "Loopback origins only; no QMS record mutations, external requests, DOM replacement, or CSS overrides.", assets }, null, 2)}\n`);
  console.log(`Captured ${assets.length} synthetic product screenshots; no QMS records were changed.`);
  console.log(JSON.stringify(assets.map(({ path: assetPath, width, height, sha256 }) => ({ path: assetPath, width, height, sha256 }))));
} finally {
  await browser.close();
}
