import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const tenant = "10000000-0000-4000-8000-000000000001";
const actor = "20000000-0000-4000-8000-000000000007";
const unitA = "30000000-0000-4000-8000-000000000001";
const unitB = "30000000-0000-4000-8000-000000000002";
const recordId = "40000000-0000-4000-8000-000000000001";
const capabilities = ["processes.read", "documents.read", "controls.read", "control_instances.read", "risks.read", "ncr.read", "capa.read", "audits.read"];
const unit = (id: string) => ({ id, tenant_id: tenant, code: id === unitA ? "SITE-A" : "SITE-B", name: "Synthetic study site", unit_type: "site", status: "active" });

async function fixture(page: Page, role = "owner") {
  const state = { status: 200, caps: capabilities, reads: [] as string[], sample: false, hold: false, held: false, released: false, release: () => {} };
  await page.route("**/api/identity/**", async route => {
    const url = new URL(route.request().url()), path = url.pathname.replace("/api/identity", "");
    const ok = (json: unknown, headers?: Record<string, string>) => route.fulfill({ json, headers });
    if (path === "/auth/me") return ok({ id: actor, display_name: "Synthetic coordinator", current_tenant_id: tenant, email: null });
    if (path === "/auth/tenants") return ok([{ id: tenant, name: "DEMO Journey Company", slug: "demo-journey", role }]);
    if (path === "/qms-access/active-capabilities") return ok({ capabilities });
    if (path === "/organization/units") return ok([unit(unitA), unit(unitB)], { "X-Tenant-ID": tenant });
    if (path.startsWith("/organization/units/")) return ok(unit(path.split("/").at(-1)!));
    if (path === "/qms-access/effective") return ok({ unit_id: url.searchParams.get("unit_id"), capabilities: state.caps });
    if (path === "/action-center") return ok({ scope: "mine", generated_at: "2026-11-18T12:00:00Z", summary: { total: 0, overdue: 0, due_soon: 0, unassigned: 0, by_source: {} }, items: [] });
    const supported = ["/processes", "/documents", "/control-instances", "/risks", "/nonconformities", "/capas", "/internal-audits/audits"];
    if (supported.includes(path)) {
      state.reads.push(path);
      const scope = url.searchParams.get("unit_id")!, code = scope === unitA ? "EXISTING-A" : "EXISTING-B";
      const row = { id: recordId, tenant_id: tenant, unit_id: scope, code, name: "Existing study record", title: "Existing study document", status: "active", current_revision_id: recordId, implementation_status: "under_review", state: path === "/internal-audits/audits" ? "planned" : path === "/nonconformities" ? "open" : path === "/capas" ? "action_planned" : "monitoring" };
      const rows = state.sample ? Array.from({ length: path === "/documents" ? 51 : 50 }, (_, i) => ({ ...row, id: `40000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`, code: `${code}-${i + 1}` })) : [row];
      if (state.hold && path === "/processes" && scope === unitA) {
        state.hold = false; state.held = true;
        await new Promise<void>(resolve => { state.release = resolve; });
        try { await route.fulfill({ json: rows }); } finally { state.released = true; }
        return;
      }
      return route.fulfill({ status: state.status, json: rows });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  return state;
}

const journeyNames = ["Build a QMS from the beginning", "Improve an existing quality system", "Transition to another ISO edition", "Move from another QMS or files", "Prepare for an audit", "Extend the scope or add sites"];

test("all six cases explain instructions, outputs and completion criteria without a fake completion checkbox", async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  await expect(guide.getByRole("combobox", { name: "Organizational unit" })).toHaveValue("");
  for (const name of journeyNames) {
    await guide.getByRole("tab", { name: new RegExp(`^${name}`) }).click();
    await expect(guide.getByRole("tabpanel")).toContainText(name);
    await expect(guide.getByRole("heading", { name: "What to do", exact: true })).toBeVisible();
    await expect(guide.getByText("Expected output", { exact: true })).toBeVisible();
    await expect(guide.getByText("Review before moving on", { exact: true })).toBeVisible();
    await guide.getByRole("button", { name: "Next step", exact: true }).click();
    await expect(guide.getByText(/^Step 2 of/)).toBeVisible();
  }
  await expect(guide.getByRole("checkbox")).toHaveCount(0);
  expect(state.reads).toEqual([]);
});

test("observed unit records never complete a project step and navigation preserves the selected unit", async ({ page }) => {
  await fixture(page);
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  await guide.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitB);
  await expect(guide.getByRole("button", { name: "Open Processes", exact: true })).toBeVisible();
  await expect(guide).toContainText("do not verify completion");
  await guide.getByText("Inspect 1 records", { exact: true }).click();
  await expect(guide.getByText("EXISTING-B", { exact: true })).toBeVisible();
  await expect(guide).not.toContainText("100%");
  await guide.getByRole("button", { name: "Open Processes", exact: true }).click();
  await expect(page).toHaveURL(/#process-title$/);
  // The existing process workspace requests its own scope list; navigation carries the root unit preference.
  await page.getByRole("link", { name: "Implementation guide", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Organizational unit" })).toHaveValue(unitB);
});

test("missing unit responsibilities are not empty records and never trigger module reads", async ({ page }) => {
  const state = await fixture(page); state.caps = [];
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  await guide.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitA);
  await expect(guide.getByText("Access required", { exact: true })).toBeVisible();
  await expect(guide.getByRole("button", { name: "Open Processes", exact: true })).toHaveCount(0);
  await expect(guide.getByText("No records found", { exact: true })).toHaveCount(0);
  expect(state.reads).toEqual([]);
});

for (const status of [401, 403]) test(`a scoped HTTP${status} clears observations and actions`, async ({ page }) => {
  const state = await fixture(page);
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  await guide.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitA);
  await expect(guide.getByRole("button", { name: "Open Processes", exact: true })).toBeVisible();
  state.status = status;
  await guide.getByRole("button", { name: "Refresh snapshot" }).click();
  await expect(guide.getByRole("alert")).toContainText(status === 401 ? "Your session has expired" : "Access required");
  await expect(guide.getByRole("button", { name: "Open Processes", exact: true })).toHaveCount(0);
  await expect(guide.getByText("Inspect 1 records", { exact: true })).toHaveCount(0);
});

test("pending capabilities remain clearly unavailable even when records exist", async ({ page }) => {
  const state = await fixture(page); state.sample = true;
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  await guide.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitA);
  await expect(guide).toContainText("Partial sample: first 50 records only");
  await guide.getByRole("button", { name: "Prepare controlled information", exact: true }).click();
  await expect(guide).toContainText("Partial sample: first 50 records only");
  await expect(guide.getByText("Inspect 50 sampled records", { exact: true })).toBeVisible();
  await guide.getByRole("tab", { name: /^Move from another/ }).click();
  await expect(guide.getByText("Feature pending", { exact: true }).last()).toBeVisible();
  await expect(guide.getByRole("button", { name: /^Open / })).toHaveCount(0);
  await expect(guide.getByRole("checkbox")).toHaveCount(0);
});

test("a previous-unit request cannot restore records after changing scope", async ({ page }) => {
  const state = await fixture(page); state.hold = true;
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  await guide.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitA);
  await expect.poll(() => state.held).toBe(true);
  await guide.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitB);
  await expect(guide.getByRole("button", { name: "Open Processes", exact: true })).toBeVisible();
  state.release();
  await expect.poll(() => state.released).toBe(true);
  await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await guide.getByText("Inspect 1 records", { exact: true }).click();
  await expect(guide.getByText("EXISTING-B", { exact: true })).toBeVisible();
  await expect(guide.getByText("EXISTING-A", { exact: true })).toHaveCount(0);
});

for (const size of [{ width: 375, height: 812 }, { width: 1280, height: 900 }]) test(`guided journey keyboard and accessibility ${size.width}`, async ({ page }, info) => {
  await fixture(page);
  await page.setViewportSize(size);
  await page.goto("/#implementation-guide-heading");
  const guide = page.getByRole("region", { name: "Implementation guide", exact: true });
  const first = guide.getByRole("tab", { name: /^Build a QMS/ });
  await first.focus(); await first.press("ArrowRight");
  await expect(guide.getByRole("tab", { name: /^Improve an existing/ })).toBeFocused();
  await guide.getByRole("tab", { name: /^Improve an existing/ }).press("Control+Home");
  await expect(guide.getByRole("tab", { name: /^Improve an existing/ })).toHaveAttribute("aria-selected", "true");
  await guide.getByRole("button", { name: "Next step", exact: true }).click();
  const detail = page.locator("#guide-step-heading");
  await expect(detail).toBeFocused();
  const headingBounds = await detail.boundingBox();
  const topbarBounds = await page.locator(".qms-app-topbar").boundingBox();
  expect(headingBounds).not.toBeNull();
  expect(topbarBounds).not.toBeNull();
  expect(headingBounds!.y).toBeGreaterThanOrEqual(topbarBounds!.y + topbarBounds!.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  const accessibility = await new AxeBuilder({ page }).include(".guided-workspace").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  await info.attach("guided-journey", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
});
