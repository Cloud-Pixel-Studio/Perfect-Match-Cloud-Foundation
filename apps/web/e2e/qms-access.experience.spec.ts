import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const tenant = "a1000000-0000-4000-8000-000000000001";
const owner = "a2000000-0000-4000-8000-000000000001";
const member = "a2000000-0000-4000-8000-000000000002";
const scope = "a3000000-0000-4000-8000-000000000001";
type Grant = {
  id: string; user_id: string; unit_id: string; capability: string; status: string;
  granted_by_user_id: string; created_at: string; revoked_by_user_id: string | null; revoked_at: string | null;
  member_name: string; unit_name: string; unit_code: string; unit_status: string;
};
type State = {
  rows: Grant[]; reads: URL[]; writes: Array<{ path: string; body: unknown }>;
  unexpected: string[]; pageStatus: number; wrongContext: boolean; mutationStatus: number;
  duplicate: boolean; role: string; wrongCatalog: boolean; persistedFailure: boolean;
};
const states = new WeakMap<Page, State>();
test.afterEach(async ({ page }) => {
  const state = states.get(page);
  if (state) expect(state.unexpected, "Every identity mutation must be intercepted").toEqual([]);
});

async function fixture(page: Page, role = "owner") {
  const actor = role === "owner" ? owner : member;
  const capabilities = ["documents.read", "documents.author", "documents.review", "documents.approve", "documents.release", "documents.obsolete", "capa.review", "evidence.review", "processes.read", "processes.manage", "controls.read", "controls.manage", "control_instances.read", "control_instances.manage", "risks.read", "risks.manage", "risks.review", "ncr.read", "ncr.manage", "ncr.review", "capa.read", "capa.manage", "evidence.read", "documents.read"];
  const rows = Array.from({ length: 24 }, (_, index): Grant => ({
    id: `a4000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    user_id: member, unit_id: scope, capability: capabilities[index], status: index === 23 ? "revoked" : "active",
    granted_by_user_id: owner, created_at: "2026-11-14T12:00:00Z",
    revoked_by_user_id: index === 23 ? owner : null, revoked_at: index === 23 ? "2026-11-14T13:00:00Z" : null,
    member_name: "Synthetic quality member", unit_name: "Receiving quality", unit_code: "REC", unit_status: "active",
  }));
  const state: State = { rows, reads: [], writes: [], unexpected: [], pageStatus: 200,
    wrongContext: false, mutationStatus: 201, duplicate: false, role, wrongCatalog: false, persistedFailure: false };
  states.set(page, state);
  await page.context().addCookies([{ name: "pm_csrf", value: "synthetic-browser-csrf", url: test.info().project.use.baseURL ?? "http://127.0.0.1:3101" }]);
  await page.route("**/api/identity/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/identity", "");
    if (request.method() !== "GET") {
      if (path === "/qms-access/grants" && request.method() === "POST") {
        const body = request.postDataJSON();
        state.writes.push({ path, body });
        if (state.mutationStatus !== 201 && !state.persistedFailure) return route.fulfill({ status: state.mutationStatus, json: { detail: "Synthetic mutation failure" } });
        const row: Grant = { ...state.rows[0], ...body, id: "a4000000-0000-4000-8000-999999999999", status: "active", revoked_by_user_id: null, revoked_at: null };
        state.rows.unshift(row);
        return route.fulfill({ status: state.mutationStatus, json: state.mutationStatus === 201 ? row : { detail: "Synthetic lost outcome after persistence" } });
      }
      const revoke = path.match(/^\/qms-access\/grants\/([a-f0-9-]+)\/revoke$/);
      if (revoke && request.method() === "POST") {
        state.writes.push({ path, body: request.postData() });
        const row = state.rows.find((item) => item.id === revoke[1]);
        if (!row) return route.fulfill({ status: 404, json: { detail: "Synthetic missing grant" } });
        Object.assign(row, { status: "revoked", revoked_by_user_id: owner, revoked_at: "2026-11-14T14:00:00Z" });
        return route.fulfill({ status: 200, json: row });
      }
      state.unexpected.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    state.reads.push(url);
    if (path === "/auth/me") return route.fulfill({ json: { id: actor, display_name: "Synthetic viewer", email: null, current_tenant_id: tenant } });
    if (path === "/auth/tenants") return route.fulfill({ json: [{ id: tenant, name: "Synthetic company", slug: "synthetic", role: state.role }] });
    if (path === "/qms-access/active-capabilities") return route.fulfill({ json: { capabilities: [] } });
    if (path === "/organization/members") return route.fulfill({ headers: { "X-Tenant-ID": state.wrongCatalog ? scope : tenant }, json: [{ id: owner, display_name: "Synthetic owner", role: "owner" }, { id: member, display_name: "Synthetic quality member", role: "member" }] });
    if (path === "/organization/units") return route.fulfill({ headers: { "X-Tenant-ID": state.wrongCatalog ? scope : tenant }, json: [{ id: scope, name: "Receiving quality", code: "REC", status: "active", unit_type: "team", tenant_id: tenant }] });
    if (path === "/qms-access/grants/page") {
      if (state.pageStatus !== 200) return route.fulfill({ status: state.pageStatus, json: { detail: "Synthetic history feedback" } });
      const params = url.searchParams;
      const limit = Number(params.get("limit") ?? 20);
      const offset = params.get("cursor") === "page-20" ? 20 : 0;
      const selected = state.rows.filter((row) =>
        (params.get("status") === "all" || !params.get("status") || row.status === params.get("status")) &&
        (!params.get("user_id") || row.user_id === params.get("user_id")) &&
        (!params.get("unit_id") || row.unit_id === params.get("unit_id")) &&
        (!params.get("capability") || row.capability === params.get("capability")) &&
        (!params.get("q") || `${row.member_name} ${row.unit_name} ${row.capability}`.toLowerCase().includes(String(params.get("q")).toLowerCase())));
      const items = limit === 1 && state.duplicate ? [{ ...state.rows[0], capability: params.get("capability") ?? "documents.read" }] : selected.slice(offset, offset + limit);
      return route.fulfill({ json: { tenant_id: tenant, viewer_user_id: state.wrongContext ? owner === actor ? member : owner : actor,
        viewer_role: state.role, items, next_cursor: limit !== 1 && selected.length > offset + limit ? "page-20" : null } });
    }
    // Unknown reads are also contained; no live API or identity provider is consulted.
    return route.fulfill({ status: 404, json: { detail: "Unimplemented synthetic read" } });
  });
  await page.goto("/#qms-access-heading");
  const panel = page.locator(".qms-access-panel");
  await expect(panel.getByRole("heading", { name: role === "owner" ? "QMS permissions" : "My QMS permissions", exact: true })).toBeVisible();
  await expect(panel.getByRole("table")).toBeVisible();
  return { state, panel };
}

for (const theme of ["light", "dark"]) for (const viewport of [{ name: "desktop", width: 1440, height: 1000 }, { name: "mobile", width: 375, height: 812 }]) {
  test(`permission history uses server pages, filters and accessible layout on ${viewport.name} in ${theme}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    await page.addInitScript((mode) => { localStorage.setItem("pm-theme", mode); document.documentElement.dataset.theme = mode; }, theme);
    const { state, panel } = await fixture(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const table = panel.getByRole("table");
    await expect(table.getByRole("row")).toHaveCount(21);
    await panel.getByRole("button", { name: "Next permissions", exact: true }).click();
    await expect(table.getByRole("row")).toHaveCount(5);
    expect(state.reads.some((url) => url.searchParams.get("cursor") === "page-20")).toBe(true);
    await panel.getByRole("button", { name: "Previous permissions", exact: true }).click();
    await expect(table.getByRole("row")).toHaveCount(21);
    const form = panel.getByRole("form", { name: "Filter permission history" });
    await form.getByRole("combobox", { name: /^Permission status\b/ }).selectOption("revoked");
    await form.getByRole("button", { name: "Apply filters", exact: true }).click();
    await expect(table.getByRole("row")).toHaveCount(2);
    expect(state.reads.findLast(url => url.pathname.endsWith("/qms-access/grants/page"))?.searchParams.get("status")).toBe("revoked");
    expect(state.reads.some((url) => url.pathname.endsWith("/qms-access/grants"))).toBe(false);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    const accessibility = await new AxeBuilder({ page }).include(".qms-access-panel").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    expect(accessibility.violations).toEqual([]);
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    await page.screenshot({ path: info.outputPath(`permission-history-${viewport.name}-${theme}.png`), fullPage: true });
    expect(state.writes).toEqual([]);
  });
}

for (const role of ["member", "admin", "auditor"]) {
  test(`${role} sees own history without tenant directory or owner controls`, async ({ page }) => {
    const { state, panel } = await fixture(page, role);
    await expect(panel.getByRole("form", { name: "Grant QMS access" })).toHaveCount(0);
    await expect(panel.getByRole("combobox", { name: /^Filter member\b/ })).toHaveCount(0);
    await expect(panel.getByRole("combobox", { name: /^Filter scope\b/ })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Revoke", exact: true })).toHaveCount(0);
    expect(state.reads.some((url) => url.pathname.endsWith("/organization/members"))).toBe(false);
    expect(state.reads.some((url) => url.pathname.endsWith("/organization/units"))).toBe(false);
    expect(state.writes).toEqual([]);
  });
}

for (const status of [403, 409, 500, 503]) {
  test(`history ${status} removes stale grants and prevents blind mutation`, async ({ page }) => {
    const { state, panel } = await fixture(page);
    state.pageStatus = status;
    await panel.getByRole("button", { name: "Refresh QMS access", exact: true }).click();
    await expect(panel.getByRole("table")).toHaveCount(0);
    if (status === 403) await expect(panel.getByRole("form", { name: "Grant QMS access" })).toHaveCount(0);
    else await expect(panel.getByRole("button", { name: "Grant access", exact: true })).toBeDisabled();
    expect(state.writes).toEqual([]);
  });
}

test("wrong viewer context is rejected without exposing rows", async ({ page }) => {
  const { state, panel } = await fixture(page);
  state.wrongContext = true;
  await panel.getByRole("button", { name: "Refresh QMS access", exact: true }).click();
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(panel.getByRole("form", { name: "Grant QMS access" })).toHaveCount(0);
  expect(state.writes).toEqual([]);
});

test("grant checks the full active scope instead of the visible history page", async ({ page }) => {
  const { state, panel } = await fixture(page);
  const form = panel.getByRole("form", { name: "Grant QMS access" });
  state.duplicate = true;
  await form.getByRole("combobox", { name: /^Member\b/ }).selectOption(member);
  await form.getByRole("combobox", { name: /^Scope\b/ }).selectOption(scope);
  await form.getByRole("combobox", { name: /^Responsibility\b/ }).selectOption("evidence.read");
  await expect.poll(() => state.reads.some((url) => url.searchParams.get("limit") === "1" && url.searchParams.get("capability") === "evidence.read")).toBe(true);
  await expect(form.getByRole("button", { name: "Grant access", exact: true })).toBeDisabled();
  expect(state.writes).toEqual([]);
});


test("owner rejects catalogues from a different company", async ({ page }) => {
  const { state, panel } = await fixture(page);
  state.wrongCatalog = true;
  await panel.getByRole("button", { name: "Refresh QMS access", exact: true }).click();
  await expect(panel.getByRole("table")).toHaveCount(0);
  await expect(panel.getByRole("form", { name: "Grant QMS access" })).toHaveCount(0);
  expect(state.writes).toEqual([]);
});

async function selectNewGrant(panel: ReturnType<Page["locator"]>) {
  const form = panel.getByRole("form", { name: "Grant QMS access" });
  await form.getByRole("combobox", { name: /^Member\b/ }).selectOption(member);
  await form.getByRole("combobox", { name: /^Scope\b/ }).selectOption(scope);
  await form.getByRole("combobox", { name: /^Responsibility\b/ }).selectOption("evidence.create");
  await expect(form.getByRole("button", { name: "Grant access", exact: true })).toBeEnabled();
  return form;
}

test("owner grants and revokes with explicit confirmation and refreshed history", async ({ page }) => {
  const { state, panel } = await fixture(page);
  const form = await selectNewGrant(panel);
  await form.getByRole("button", { name: "Grant access", exact: true }).click();
  await expect(panel.getByText("Access granted. The change has been recorded in the audit trail.", { exact: true })).toBeVisible();
  const row = panel.getByRole("row").filter({ hasText: "Create evidence" });
  await expect(row).toHaveCount(1);
  await row.getByRole("button", { name: "Revoke", exact: true }).click();
  expect(state.writes).toHaveLength(1);
  await row.getByRole("button", { name: "Confirm revoke", exact: true }).click();
  await expect(panel.getByText("Access revoked. The original grant remains in the history.", { exact: true })).toBeVisible();
  await expect(row.getByText("Revoked", { exact: true })).toBeVisible();
  expect(state.writes).toHaveLength(2);
});

test("persisted grant followed by 500 blocks resending until explicit reconciliation", async ({ page }) => {
  const { state, panel } = await fixture(page);
  const form = await selectNewGrant(panel);
  state.mutationStatus = 500; state.persistedFailure = true;
  await form.getByRole("button", { name: "Grant access", exact: true }).click();
  await expect(panel.getByRole("alert")).toContainText("save outcome is unconfirmed");
  await expect(form.getByRole("button", { name: "Grant access", exact: true })).toBeDisabled();
  expect(state.writes).toHaveLength(1);
  await panel.getByRole("button", { name: "Refresh QMS access", exact: true }).click();
  await expect(panel.getByRole("row").filter({ hasText: "Create evidence" })).toHaveCount(1);
  await expect(form.getByRole("button", { name: "Grant access", exact: true })).toBeDisabled();
  expect(state.writes).toHaveLength(1);
});
