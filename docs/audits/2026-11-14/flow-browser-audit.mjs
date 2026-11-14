// Read-only browser audit. QMS mutations are blocked; explicit mock cases stay in memory.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(resolve("apps/web/package.json"));
const { chromium, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const base = process.env.FLOW_WEB_URL ?? "http://127.0.0.1:3103";
const api = process.env.FLOW_API_URL ?? "http://127.0.0.1:8000";
const out = resolve("artifacts/complete-flow-audit-20261114");
const shots = resolve("docs/audits/2026-11-14/screenshots");
await mkdir(out, { recursive: true });
await mkdir(shots, { recursive: true });
const report = { startedAt: new Date().toISOString(), base, api, qmsWritesForwarded: 0, cases: [], roles: [] };
const healthResponse = await fetch(`${api}/health`);
report.runtimeHealth = { checkedAt: new Date().toISOString(), status: healthResponse.status, body: await healthResponse.json() };
const browser = await chromium.launch({ headless: true });

async function run(name, evidence, operation) {
  try {
    const detail = await operation();
    report.cases.push({ name, evidence, result: "PASS", detail });
  } catch (error) {
    report.cases.push({ name, evidence, result: "FAIL", error: String(error.message).slice(0, 1500) });
  }
  await writeFile(resolve(out, "browser-results.json"), JSON.stringify(report, null, 2));
}

async function layout(page, screenshot) {
  await page.evaluate(() => document.fonts.ready);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  if (screenshot) await page.screenshot({ path: resolve(shots, screenshot), fullPage: true });
  assert(overflow <= 1, `Horizontal overflow: ${overflow}px`);
  assert.deepEqual(axe.violations.map(({ id, impact, nodes }) => ({ id, impact, count: nodes.length })), []);
  return { overflow, axeViolations: axe.violations.length };
}

async function readonly(page, blocked) {
  await page.route("**/api/identity/**", route => {
    if (["GET", "HEAD"].includes(route.request().method())) return route.continue();
    blocked.push({ method: route.request().method(), path: new URL(route.request().url()).pathname });
    return route.fulfill({ status: 409, json: { detail: "QMS mutation blocked by read-only flow audit" } });
  });
}

async function authenticate(page, user, key) {
  assert(process.env[key], `Missing development credential: ${key}`);
  await page.goto(`${base}/api/identity/auth/login`);
  await page.locator("#username").fill(user);
  await page.locator("#password").fill(process.env[key]);
  await Promise.all([
    page.waitForURL(url => url.origin === "http://127.0.0.1:3000", { timeout: 30000 }),
    page.locator("#kc-login").click(),
  ]);
  // The approved local OIDC callback remains on port3000. Only the UI preview uses3103.
  await page.goto(base, { waitUntil: "networkidle" });
  await expect(page.getByRole("navigation", { name: "QMS modules" })).toBeVisible();
}

async function chooseUnit(page) {
  const select = page.locator("#qms-active-workspace > section select").first();
  if (!await select.isVisible()) return;
  const options = select.locator('option:not([disabled])[value]:not([value=""])');
  if (await options.count() && !await select.inputValue()) {
    await select.selectOption(await options.first().getAttribute("value"));
    await page.waitForLoadState("networkidle");
  }
}

const publicContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
const publicPage = await publicContext.newPage();
await run("marketing: product tour, demo intent and download", "real frontend; no message sent", async () => {
  await publicPage.goto(`${base}/products`, { waitUntil: "networkidle" });
  const documents = publicPage.getByRole("tab", { name: "Document control" });
  await documents.focus(); await publicPage.keyboard.press("ArrowRight");
  await expect(publicPage.getByRole("tab", { name: "Risks & opportunities" })).toBeFocused();
  await expect(publicPage.getByRole("tabpanel")).toHaveAccessibleName("Risks & opportunities");
  const email = publicPage.getByRole("link", { name: "Prepare demo email", exact: true });
  await publicPage.getByRole("spinbutton", { name: "Team seats" }).fill("0");
  await expect(email).not.toHaveAttribute("href");
  await expect(publicPage.getByRole("button", { name: "Download brief" })).toBeDisabled();
  await publicPage.getByRole("spinbutton", { name: "Team seats" }).fill("3");
  await publicPage.getByRole("textbox", { name: "Company" }).fill("Synthetic Flow Audit Company");
  await publicPage.getByRole("checkbox", { name: "ISO 9001 In preparation", exact: true }).check();
  const mailto = new URL(await email.getAttribute("href"));
  assert.equal(mailto.protocol, "mailto:"); assert.equal(mailto.pathname, "Demo@invperfectmatch.com");
  assert.match(mailto.searchParams.get("body"), /Team seats: 3/);
  const downloadEvent = publicPage.waitForEvent("download");
  await publicPage.getByRole("button", { name: "Download brief" }).click();
  const download = await downloadEvent;
  assert.equal(await download.failure(), null);
  assert.equal(download.suggestedFilename(), "perfect-match-qms-demo-brief.txt");
  await publicPage.evaluate(() => window.scrollTo(0, 0));
  return { ...await layout(publicPage, "marketing-desktop.png"), contact: mailto.pathname, transmission: "not tested; mail client intentionally not opened", onboarding: "not available" };
});
await run("marketing: 320px keyboard FAQ and navigation", "real frontend", async () => {
  await publicPage.setViewportSize({ width: 320, height: 740 });
  await publicPage.goto(`${base}/products`, { waitUntil: "networkidle" });
  await publicPage.getByRole("navigation", { name: "Product navigation" }).getByRole("link", { name: "Security", exact: true }).click();
  await expect(publicPage.getByRole("heading", { name: "Your quality data. Clear boundaries." })).toBeInViewport();
  const question = publicPage.locator("summary").filter({ hasText: "Is a seat the same as approval authority?" });
  await question.focus(); await publicPage.keyboard.press("Enter");
  await expect(question.locator("..")).toHaveAttribute("open", "");
  return layout(publicPage);
});
await run("anonymous entry reaches the approved login boundary", "real frontend; no authentication yet", async () => {
  await publicPage.goto(base, { waitUntil: "networkidle" });
  await expect(publicPage.getByRole("heading", { name: "Welcome to Perfect Match" })).toBeVisible();
  await expect(publicPage.getByRole("link", { name: "Continue to Perfect Match" })).toHaveAttribute("href", "/api/identity/auth/login");
  return layout(publicPage, "login-mobile.png");
});
await publicContext.close();

const modules = [
  ["overview-heading", "overview"], ["action-center-heading", "actions"], ["workflow-heading", "workflows"],
  ["process-title", "processes"], ["documents-heading", "documents"], ["controls-heading", "controls"],
  ["internal-audits-heading", "internal-audits"], ["risks-heading", "risks"], ["ncr-heading", "ncr"],
  ["capa-heading", "capa"], ["organization-workspace-heading", "organization"],
  ["qms-access-heading", "permissions"], ["audit-heading", "audit-trail"],
];

if (report.runtimeHealth.status !== 200) {
  report.cases.push({ name: "real OIDC and business GET navigation", evidence: "actual health endpoint", result: "BLOCKED", detail: "Database unavailable; no credential submitted and no business request attempted." });
}
for (const [role, user, key] of (report.runtimeHealth.status === 200 ? [["member", "pmc-user-a", "KEYCLOAK_USER_A_PASSWORD"], ["owner", "pmc-local-owner", "KEYCLOAK_OWNER_PASSWORD"]] : [])) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
  const page = await context.newPage(); const blocked = [];
  await readonly(page, blocked);
  let authenticated = false;
  await run(`${role}: actual OIDC authentication and company selection display`, "real OIDC development session and GET APIs", async () => {
    await authenticate(page, user, key); authenticated = true;
    const navigation = await page.getByRole("navigation", { name: "QMS modules" }).getByRole("link").allTextContents();
    const organizations = await page.getByRole("combobox", { name: "Current organization", exact: true }).locator("option").allTextContents();
    report.roles.push({ role, navigation, organizations });
    return { navigation, organizations, ...await layout(page, role === "member" ? "workspace-member-desktop.png" : null) };
  });
  if (!authenticated) { await context.close(); continue; }
  const visible = new Set(await page.getByRole("navigation", { name: "QMS modules" }).getByRole("link").evaluateAll(links => links.map(link => new URL(link.href).hash.slice(1))));
  for (const [hash, name] of modules.filter(([hash]) => visible.has(hash))) {
    await run(`${role}: ${name} reads and accessible desktop layout`, "real runtime0048 GET APIs; source PR41 frontend", async () => {
      const responses = []; const listener = response => { if (response.url().includes("/api/identity/")) responses.push({ path: new URL(response.url()).pathname.replace("/api/identity", ""), status: response.status() }); };
      page.on("response", listener);
      try {
        await page.goto(`${base}/#${hash}`, { waitUntil: "networkidle" });
        await chooseUnit(page);
        await expect(page.locator(`#${hash}`)).toBeVisible();
        if (name === "internal-audits") {
          await page.getByRole("tab", { name: "Scheduled audits", exact: true }).click();
          await page.waitForLoadState("networkidle");
          const record = page.locator(".ncr-record-list button").first();
          if (await record.count()) {
            await record.click(); await page.waitForLoadState("networkidle");
            const readiness = page.getByRole("tab", { name: "Readiness", exact: true });
            if (await readiness.count()) { await readiness.click(); await page.waitForLoadState("networkidle"); }
          }
        }
        return { headings: await page.locator("#qms-active-workspace").getByRole("heading").allTextContents(), alerts: await page.locator("#qms-active-workspace [role=alert]").allTextContents(), statuses: await page.locator("#qms-active-workspace [role=status]").allTextContents(), responses, ...await layout(page, name === "internal-audits" ? "audits-readiness-desktop.png" : role === "owner" && name === "permissions" ? "permissions-owner-desktop.png" : null) };
      } finally { page.off("response", listener); }
    });
  }
  await run(`${role}: mobile375 dark module navigation`, "real runtime0048 GET APIs", async () => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${base}/#${role === "member" ? "documents-heading" : "organization-workspace-heading"}`, { waitUntil: "networkidle" });
    await chooseUnit(page);
    await page.getByRole("checkbox", { name: "Use dark theme" }).check();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    const moduleSelect = page.getByLabel("Module", { exact: true });
    await expect(moduleSelect).toBeVisible();
    await moduleSelect.selectOption("actions");
    await expect(page.locator("#action-center-heading")).toBeVisible();
    return layout(page, `${role}-actions-mobile-dark.png`);
  });
  await run(`${role}: 503 action-center read error`, "HTTP response mocked in browser memory; QMS backend unchanged", async () => {
    await page.route("**/api/identity/action-center?**", route => route.fulfill({ status: 503, json: { detail: "Isolated synthetic outage" } }));
    await page.getByRole("button", { name: "Refresh action center", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("temporarily unavailable");
    return { alert: await page.getByRole("alert").textContent(), ...await layout(page) };
  });
  assert.deepEqual(blocked, [], "Read-only scenarios must not attempt QMS mutations");
  await context.close();
}

// Synthetic role checks exercise presentation only, not server authorization.
for (const [role, caps, expected] of [["auditor", ["audits.read", "documents.read"], ["Internal audits", "Documents", "Organization", "Audit trail"]], ["member", [], []]]) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); const writes = [];
  await page.route("**/api/identity/**", route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace("/api/identity", "");
    if (request.method() !== "GET") { writes.push(path); return route.fulfill({ status: 409, json: { detail: "Mock role mutation blocked" } }); }
    if (path === "/auth/me") return route.fulfill({ json: { id: "11111111-1111-4111-8111-111111111111", display_name: "Synthetic role presentation", email: null, current_tenant_id: "22222222-2222-4222-8222-222222222222" } });
    if (path === "/auth/tenants") return route.fulfill({ json: [{ id: "22222222-2222-4222-8222-222222222222", name: "Synthetic Company", slug: "synthetic-company", role }] });
    if (path === "/qms-access/active-capabilities") return route.fulfill({ json: { capabilities: caps } });
    if (path === "/action-center") return route.fulfill({ json: { scope: "mine", generated_at: new Date().toISOString(), summary: { total: 0, overdue: 0, due_soon: 0, unassigned: 0, by_source: {} }, items: [] } });
    return route.fulfill({ status: 403, json: { detail: "Not supplied by isolated role fixture" } });
  });
  await run(`synthetic ${role}: capability-segregated navigation`, "in-memory identity/capabilities; not a server authorization test", async () => {
    await page.goto(`${base}/#capa-heading`, { waitUntil: "networkidle" });
    const navigation = await page.getByRole("navigation", { name: "QMS modules" }).getByRole("link").allTextContents();
    for (const label of expected) assert(navigation.includes(label), `Missing ${label}`);
    assert(!navigation.includes("Corrective actions"));
    await expect(page.getByRole("heading", { name: "Work with clarity." })).toBeVisible();
    if (role === "member") assert.deepEqual(navigation, ["Overview", "Action center", "Workflows", "Permissions"]);
    assert.deepEqual(writes, []);
    return { navigation, directLink: "unauthorized module falls back to overview", ...await layout(page) };
  });
  await context.close();
}

await browser.close();
report.finishedAt = new Date().toISOString();
report.summary = { pass: report.cases.filter(item => item.result === "PASS").length, fail: report.cases.filter(item => item.result === "FAIL").length, blocked: report.cases.filter(item => item.result === "BLOCKED").length };
await writeFile(resolve(out, "browser-results.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ summary: report.summary, failed: report.cases.filter(item => item.result === "FAIL").map(({ name, error }) => ({ name, error })), qmsWritesForwarded: report.qmsWritesForwarded }));
process.exitCode = report.summary.fail ? 1 : 0;
