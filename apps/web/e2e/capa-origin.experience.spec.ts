import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { authenticateWithKeycloak } from "./support/auth";

const password = process.env.KEYCLOAK_USER_A_PASSWORD;

test("live seeded NCR opens its persisted corrective action without QMS writes", async ({ page }, testInfo) => {
  test.skip(!password, "Synthetic development credential was not provided");
  await authenticateWithKeycloak(page, { username: "pmc-user-a", password: String(password) });
  const writes: string[] = [];
  await page.route("**/api/identity/**", async (route) => {
    if (route.request().method() !== "GET") {
      writes.push(`${route.request().method()} ${new URL(route.request().url()).pathname}`);
      return route.abort("blockedbyclient");
    }
    return route.fallback();
  });
  await page.goto("/#ncr-heading", { waitUntil: "networkidle" });
  const panel = page.locator('section[aria-labelledby="ncr-heading"]');
  const unit = panel.getByRole("combobox", { name: "Organization scope" });
  const demoUnit = unit.locator("option").filter({ hasText: "DEV-ACCESS-UI" });
  await expect(demoUnit).toHaveCount(1);
  await unit.selectOption(String(await demoUnit.getAttribute("value")));
  await panel.getByRole("textbox", { name: "Find by code or title" }).fill("DEMO-NCR-001");
  await panel.getByRole("button", { name: "Search records", exact: true }).click();
  const related = panel.getByRole("region", { name: "Corrective actions from this record" });
  const open = related.getByRole("link", { name: "Open CAPA DEMO-CAPA-001", exact: true });
  await expect(open).toBeVisible();
  const screenshot = testInfo.outputPath("live-ncr-related-capa.png");
  await related.screenshot({ path: screenshot });
  await testInfo.attach("live-NCR-related-CAPA", { path: screenshot, contentType: "image/png" });
  await open.click();
  await expect(page.locator('section[aria-labelledby="capa-heading"] .ncr-detail')).toContainText("DEMO-CAPA-001");
  expect(writes).toEqual([]);
});

const unitA = "11111111-1111-4111-8111-111111111111";
const unitB = "22222222-2222-4222-8222-222222222222";
const processId = "33333333-3333-4333-8333-333333333333";
const sourceA = "44444444-4444-4444-8444-444444444444";
const sourceB = "55555555-5555-4555-8555-555555555555";
const capaId = "66666666-6666-4666-8666-666666666666";
const caps = ["ncr.read", "risks.read", "processes.read", "capa.read", "capa.manage"];
type Kind = "ncr" | "risk";
type State = {
  capabilities: string[]; getStatus: number; postStatus: number; mismatch: boolean; paged: boolean; hold: boolean;
  sourceState: string; relatedReads: Array<{ unit: string | null; ncr: string | null; risk: string | null; limit: string | null; offset: string | null }>;
  posts: Record<string, unknown>[]; unexpectedWrites: string[]; created: Record<string, unknown> | null;
};
const states = new WeakMap<Page, State>();
test.afterEach(async ({ page }) => {
  const state = states.get(page);
  if (state) expect(state.unexpectedWrites, "Fixtures must intercept every QMS mutation").toEqual([]);
});
function source(kind: Kind, id: string, unit: string, state: string) {
  return {
    id, unit_id: unit, process_id: processId, code: `SOURCE-${unit === unitA ? "A" : "B"}`,
    name: `Synthetic ${kind} source`, description: "Synthetic condition requiring controlled follow-up.",
    state, row_version: 1, owner_user_id: null, target_date: "2026-12-01",
    source_type: "internal", severity: "minor", detected_date: "2026-01-01", detected_by_user_id: null,
    containment_required: false, containment_completed: false, containment_action: "", containment_owner_user_id: null,
    containment_date: null, disposition: null, disposition_notes: "", root_cause_summary: "", closure_notes: "", cancellation_reason: "",
    opened_by_user_id: null, opened_at: null, reviewed_by_user_id: null, reviewed_at: null,
    closed_by_user_id: null, closed_at: null, cancelled_by_user_id: null, cancelled_at: null,
    is_overdue: false, days_overdue: 0, risk_type: "risk", category: "operational", source: "Synthetic source",
    cause: "", potential_effect: "", benefit: "", opportunity_action: "", mitigation_plan: "",
    likelihood: 2, impact: 2, residual_likelihood: 1, residual_impact: 1, response_strategy: "mitigate",
    review_date: null, scoring_model: "5x5-v1", initial_score: 4, initial_level: "low",
    residual_score: 1, residual_level: "low", assessed_at: null,
  };
}
function capa(kind: Kind, id = sourceA, unit = unitA, code = "RELATED-CAPA", recordId = capaId) {
  return {
    id: recordId, unit_id: unit, process_id: processId, code, name: "Synthetic corrective action",
    state: "draft", source_type: kind, source_ncr_id: kind === "ncr" ? id : null,
    source_risk_id: kind === "risk" ? id : null, source_code: `SOURCE-${unit === unitA ? "A" : "B"}`,
    source_state: "draft", source_reference: "", target_date: "2026-12-01", owner_user_id: null,
    root_cause_method: null, row_version: 1, problem_statement: "Synthetic corrective action problem.",
    analysis_data: {}, analysis_summary: "", verified_root_cause: "", other_method_name: "",
    analysis_started_at: null, plan_summary: "", planned_by_user_id: null, planned_at: null,
    implementation_started_by_user_id: null, implementation_started_at: null,
    review_started_by_user_id: null, review_started_at: null, effective_by_user_id: null, effective_at: null,
    closed_by_user_id: null, closed_at: null, closure_notes: "", cancelled_by_user_id: null,
    cancelled_at: null, cancellation_reason: "",
  };
}
async function fixture(page: Page, kind: Kind, options: { capabilities?: string[]; sourceState?: string } = {}) {
  await authenticateWithKeycloak(page, { username: "pmc-user-a", password: String(password) });
  const state: State = {
    capabilities: options.capabilities ?? [...caps], getStatus: 200, postStatus: 201,
    mismatch: false, paged: false, hold: false, sourceState: options.sourceState ?? "draft",
    relatedReads: [], posts: [], unexpectedWrites: [], created: null,
  };
  states.set(page, state);
  let markPending = () => {}; let releaseRead = () => {}; let markSettled = () => {};
  const pending = new Promise<void>((resolve) => { markPending = resolve; });
  const gate = new Promise<void>((resolve) => { releaseRead = resolve; });
  const settled = new Promise<void>((resolve) => { markSettled = resolve; });
  await page.route("**/api/identity/**", async (route) => {
    const request = route.request(); const url = new URL(request.url());
    const path = url.pathname.replace("/api/identity", ""); const method = request.method();
    if (method !== "GET") {
      if (method === "POST" && path === "/capas") {
        const body = request.postDataJSON() as Record<string, unknown>;
        state.posts.push(body);
        if (state.postStatus === 403) state.capabilities = state.capabilities.filter((value) => value !== "capa.read");
        if (state.postStatus === 201) state.created = { ...capa(kind), ...body, id: capaId };
        return route.fulfill({ status: state.postStatus, json: state.created ?? { detail: "Synthetic creation feedback" } });
      }
      state.unexpectedWrites.push(`${method} ${path}`); return route.abort("blockedbyclient");
    }
    const unit = url.searchParams.get("unit_id") ?? unitA;
    const sourceId = unit === unitA ? sourceA : sourceB;
    let body: unknown;
    if (path === "/organization/units") body = [
      { id: unitA, code: "SOURCE-A", name: "Synthetic source unit A", status: "active" },
      { id: unitB, code: "SOURCE-B", name: "Synthetic source unit B", status: "active" },
    ];
    else if (path === "/qms-access/effective") body = { unit_id: unit, capabilities: state.capabilities };
    else if (path === "/organization/members") body = [];
    else if (path === "/processes" || path === `/processes/${processId}`) {
      const process = { id: processId, code: "SOURCE-PROCESS", name: "Synthetic controlled process", status: "active" };
      body = path === "/processes" ? [process] : process;
    } else if (path === "/nonconformities" || path === "/risks") body = [source(kind, sourceId, unit, state.sourceState)];
    else if (/^\/(nonconformities|risks)\/[^/]+\/(risk|control|document|evidence)-links$/.test(path)) body = [];
    else if (path === "/capas" && (url.searchParams.has("source_ncr_id") || url.searchParams.has("source_risk_id"))) {
      state.relatedReads.push({ unit, ncr: url.searchParams.get("source_ncr_id"), risk: url.searchParams.get("source_risk_id"), limit: url.searchParams.get("limit"), offset: url.searchParams.get("offset") });
      if (state.hold && unit === unitA) {
        markPending(); await gate;
        try { await route.fulfill({ status: 200, json: [capa(kind, sourceA, unitA, "LATE-A-CAPA")] }); }
        catch (cause) { if (!request.failure()) throw cause; }
        finally { markSettled(); } return;
      }
      if (state.getStatus !== 200) return route.fulfill({ status: state.getStatus, json: { detail: "Synthetic related-list feedback" } });
      if (state.mismatch) body = [capa(kind, sourceB, unitB, "UNRELATED-CAPA")];
      else if (state.paged) body = url.searchParams.get("offset") === "20"
        ? [capa(kind, sourceId, unit, "RELATED-21")]
        : Array.from({ length: 21 }, (_, index) => capa(kind, sourceId, unit, `RELATED-${index + 1}`, `70000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`));
      else body = [state.created ?? capa(kind, sourceId, unit, unit === unitA ? "RELATED-CAPA" : "UNIT-B-CAPA")];
    } else if (path === "/capas") body = [state.created ?? capa(kind)];
    else if (path === `/capas/${capaId}`) body = state.created ?? capa(kind);
    else if (/^\/capas\/[^/]+\/(actions|effectiveness-reviews)$/.test(path)) body = [];
    else return route.fallback();
    return route.fulfill({ status: 200, json: body });
  });
  await page.goto(kind === "ncr" ? "/#ncr-heading" : "/#risks-heading", { waitUntil: "networkidle" });
  const panel = page.locator(`section[aria-labelledby="${kind === "ncr" ? "ncr" : "risks"}-heading"]`);
  const related = panel.getByRole("region", { name: "Corrective actions from this record" });
  await expect(panel.getByRole("heading", { name: `Synthetic ${kind} source` })).toBeVisible();
  return { state, panel, related, pending, release: async () => {
    releaseRead(); await settled;
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  } };
}
test.describe("CAPA from source fixtures (no backend mutations)", () => {
  test.beforeEach(() => test.skip(!password, "Synthetic development credential was not provided"));
  for (const kind of ["ncr", "risk"] as const) {
    test(`${kind} shows exact related actions and opens the selected CAPA`, async ({ page }) => {
      const { state, related } = await fixture(page, kind);
      const open = related.getByRole("link", { name: "Open CAPA RELATED-CAPA", exact: true });
      await expect(open).toHaveAttribute("href", `/?pm_source=capa&pm_record=${capaId}&pm_unit=${unitA}#capa-heading`);
      expect(state.relatedReads).toContainEqual({ unit: unitA, ncr: kind === "ncr" ? sourceA : null, risk: kind === "risk" ? sourceA : null, limit: "21", offset: "0" });
      await open.click();
      await expect(page.locator('section[aria-labelledby="capa-heading"] .ncr-detail')).toContainText("RELATED-CAPA");
      expect(state.posts).toEqual([]);
    });
    test(`${kind} creates once with the source and process fixed`, async ({ page }) => {
      const { state, related } = await fixture(page, kind);
      await related.getByRole("button", { name: "Create CAPA", exact: true }).click();
      const form = related.getByRole("form", { name: "Create corrective action" });
      await expect(form.getByLabel("CAPA title", { exact: true })).toHaveValue(`Synthetic ${kind} source`);
      await expect(form.getByRole("textbox", { name: "Problem statement", exact: true })).toHaveValue("Synthetic condition requiring controlled follow-up.");
      await form.getByLabel("CAPA code", { exact: true }).fill(`NEW-${kind.toUpperCase()}`);
      await form.getByRole("button", { name: "Create corrective action", exact: true }).click();
      await expect(form).toHaveCount(0);
      await expect(related.getByRole("status")).toContainText(`CAPA NEW-${kind.toUpperCase()} was created`);
      expect(state.posts).toEqual([{
        unit_id: unitA, process_id: processId, code: `NEW-${kind.toUpperCase()}`, name: `Synthetic ${kind} source`,
        source_type: kind, source_ncr_id: kind === "ncr" ? sourceA : null, source_risk_id: kind === "risk" ? sourceA : null,
        source_reference: "SOURCE-A", problem_statement: "Synthetic condition requiring controlled follow-up.",
        owner_user_id: null, target_date: "2026-12-01", root_cause_method: null,
      }]);
      await expect(related.getByRole("link", { name: `Open CAPA NEW-${kind.toUpperCase()}`, exact: true }).first()).toBeVisible();
    });
  }
  test("a failed creation preserves the draft and never retries automatically", async ({ page }) => {
    const { state, related } = await fixture(page, "ncr"); state.postStatus = 503;
    await related.getByRole("button", { name: "Create CAPA", exact: true }).click();
    const form = related.getByRole("form", { name: "Create corrective action" });
    await form.getByLabel("CAPA code", { exact: true }).fill("DRAFT-PRESERVED");
    await form.getByLabel("CAPA title", { exact: true }).fill("Keep this investigation draft");
    await form.getByRole("button", { name: "Create corrective action", exact: true }).click();
    await expect(related.getByRole("alert")).toContainText("temporarily unavailable");
    await expect(form.getByLabel("CAPA code", { exact: true })).toHaveValue("DRAFT-PRESERVED");
    await expect(form.getByLabel("CAPA title", { exact: true })).toHaveValue("Keep this investigation draft");
    await related.getByRole("button", { name: "Refresh related CAPA", exact: true }).click();
    await expect(related.locator(".related-capa-list")).toContainText("RELATED-CAPA"); expect(state.posts).toHaveLength(1);
  });
  test("an unconfirmed success cannot be resubmitted after cancel or refresh", async ({ page }) => {
    const { state, related } = await fixture(page, "ncr"); state.postStatus = 202;
    await related.getByRole("button", { name: "Create CAPA", exact: true }).click();
    const form = related.getByRole("form", { name: "Create corrective action" });
    await form.getByLabel("CAPA code", { exact: true }).fill("UNCERTAIN-CAPA");
    await form.getByRole("button", { name: "Create corrective action", exact: true }).click();
    await expect(related.getByRole("alert")).toContainText("could not be confirmed");
    await expect(form.getByRole("button", { name: "Create corrective action", exact: true })).toBeDisabled();
    await expect(form.getByLabel("CAPA code", { exact: true })).toHaveValue("UNCERTAIN-CAPA");
    await form.getByRole("button", { name: "Cancel CAPA", exact: true }).click();
    await related.getByRole("button", { name: "Refresh related CAPA", exact: true }).click();
    await expect(related.locator(".related-capa-list")).toContainText("RELATED-CAPA");
    await related.getByRole("button", { name: "Create CAPA", exact: true }).click();
    await expect(form.getByRole("button", { name: "Create corrective action", exact: true })).toBeDisabled();
    await expect(related.getByRole("status")).toContainText("Creation outcome is unconfirmed");
    expect(state.posts).toHaveLength(1);
  });
  test("permission denial clears source-action data and the creation form", async ({ page }) => {
    const { state, panel, related } = await fixture(page, "risk"); state.postStatus = 403;
    await related.getByRole("button", { name: "Create CAPA", exact: true }).click();
    const form = related.getByRole("form", { name: "Create corrective action" });
    await form.getByLabel("CAPA code", { exact: true }).fill("DENIED-DRAFT");
    await form.getByRole("button", { name: "Create corrective action", exact: true }).click();
    await expect(panel.getByRole("form", { name: "Create corrective action" })).toHaveCount(0);
    await expect(panel.getByRole("link", { name: "Open CAPA RELATED-CAPA", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Create CAPA", exact: true })).toHaveCount(0); expect(state.posts).toHaveLength(1);
  });
  test("responsibilities gate reading and creation independently", async ({ page }) => {
    const { state, panel, related } = await fixture(page, "ncr", { capabilities: caps.filter((value) => value !== "capa.manage") });
    await expect(related.locator(".related-capa-list")).toContainText("RELATED-CAPA");
    await expect(related.getByRole("button", { name: "Create CAPA", exact: true })).toHaveCount(0);
    state.capabilities = state.capabilities.filter((value) => value !== "capa.read");
    await panel.getByRole("button", { name: "Refresh nonconformities", exact: true }).click(); await expect(related).toHaveCount(0);
    const count = state.relatedReads.length;
    await panel.getByRole("combobox", { name: "Organization scope" }).selectOption(unitB);
    await expect(panel.getByRole("heading", { name: "Synthetic ncr source" })).toBeVisible();
    expect(state.relatedReads).toHaveLength(count); expect(state.posts).toEqual([]);
  });
  test("unrelated results are rejected if an older API ignores the filter", async ({ page }) => {
    const { state, related } = await fixture(page, "ncr"); state.mismatch = true;
    await related.getByRole("button", { name: "Refresh related CAPA", exact: true }).click();
    await expect(related.getByRole("alert")).toContainText("did not match this source");
    await expect(related.getByRole("link")).toHaveCount(0); await expect(related).not.toContainText("UNRELATED-CAPA"); expect(state.posts).toEqual([]);
  });
  test("related pagination uses the source filter on every page", async ({ page }) => {
    const { state, related } = await fixture(page, "risk"); state.paged = true;
    await related.getByRole("button", { name: "Refresh related CAPA", exact: true }).click();
    await expect(related.locator(".related-capa-list li")).toHaveCount(20);
    const pages = related.getByRole("navigation", { name: "Related CAPA pages" });
    await pages.getByRole("button", { name: "More actions", exact: true }).click();
    await expect(related.locator(".related-capa-list li")).toHaveCount(1); await expect(pages).toContainText("Showing 21–21");
    expect(state.relatedReads.at(-1)).toEqual({ unit: unitA, ncr: null, risk: sourceA, limit: "21", offset: "20" });
    await pages.getByRole("button", { name: "Previous actions", exact: true }).click();
    await expect(related.locator(".related-capa-list li")).toHaveCount(20); expect(state.posts).toEqual([]);
  });
  test("a late read cannot repopulate a different organization scope", async ({ page }) => {
    const { state, panel, related, pending, release } = await fixture(page, "ncr"); state.hold = true;
    await related.getByRole("button", { name: "Refresh related CAPA", exact: true }).click(); await pending;
    await panel.getByRole("combobox", { name: "Organization scope" }).selectOption(unitB);
    await expect(related.locator(".related-capa-list")).toContainText("UNIT-B-CAPA"); await release();
    await expect(related).not.toContainText("LATE-A-CAPA"); expect(state.relatedReads.at(-1)?.unit).toBe(unitB); expect(state.posts).toEqual([]);
  });
  test("cancelled sources preserve historical actions without a creation command", async ({ page }) => {
    const { state, related } = await fixture(page, "ncr", { sourceState: "cancelled" });
    await expect(related.locator(".related-capa-list")).toContainText("RELATED-CAPA");
    await expect(related).toContainText("Existing CAPA remain available for traceability");
    await expect(related.getByRole("button", { name: "Create CAPA", exact: true })).toHaveCount(0); expect(state.posts).toEqual([]);
  });
  test("related actions and their form fit mobile and desktop with accessible names", async ({ page }, testInfo) => {
    const { related } = await fixture(page, "risk"); await related.getByRole("button", { name: "Create CAPA", exact: true }).click();
    for (const width of [375, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(related.getByRole("form", { name: "Create corrective action" })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      const accessibility = await new AxeBuilder({ page }).include(".related-capas").withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(accessibility.violations).toEqual([]);
      await testInfo.attach(`source-CAPA-${width}`, { body: await related.screenshot(), contentType: "image/png" });
    }
  });
});
