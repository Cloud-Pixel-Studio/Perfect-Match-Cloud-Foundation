import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { authenticateWithKeycloak } from "./support/auth";

const password = process.env.KEYCLOAK_USER_A_PASSWORD;
const unitA = "11111111-1111-4111-8111-111111111111";
const unitB = "22222222-2222-4222-8222-222222222222";
const programA = "33333333-3333-4333-8333-333333333333";
const programB = "33333333-3333-4333-8333-333333333334";
const auditA = "44444444-4444-4444-8444-444444444444";
const auditB = "44444444-4444-4444-8444-444444444445";
const memberA = "55555555-5555-4555-8555-555555555555";
const actorId = "66666666-6666-4666-8666-666666666666";
const createdId = "77777777-7777-4777-8777-777777777777";
const capabilities = ["audits.read", "audits.manage", "audits.review", "audits.execute"];
type Kind = "programs" | "audits";
type Row = { id: string; unit_id: string; code: string; name: string; state: string; row_version: number; [key: string]: unknown };
type ScopeRow = { id: string; audit_id: string; unit_id: string; sequence: number; title: string; description: string; process_id: string | null; status: string; row_version: number; withdrawal_reason: string };
type CriterionRow = Omit<ScopeRow,"description"|"process_id"> & { requirement:string; source_type:string; reference:string; scope_id:string|null };
type Mutation = { method: string; path: string; body: Record<string, unknown> };
type FixtureState = {
  capabilities: string[]; programs: Row[]; audits: Row[]; writeStatus: number | null;
  conflict: boolean; hold: boolean; reads: Array<{ path: string; query: Record<string, string> }>;
  writes: Mutation[]; unexpectedWrites: string[]; scopes: ScopeRow[]; scopeMismatch: boolean; criteria: CriterionRow[]; criterionMismatch: boolean;
};
const fixtures = new WeakMap<Page, FixtureState>();
test.afterEach(async ({ page }) => {
  const state = fixtures.get(page);
  if (!state) return;
  expect(state.unexpectedWrites, "Planning fixtures must intercept every QMS mutation").toEqual([]);
  for (const read of state.reads.filter((read) => read.path === "/internal-audits/audits")) {
    expect(read.query).not.toHaveProperty("q");
    expect(read.query).not.toHaveProperty("program_id");
  }
});
function base(id: string, unit: string, code: string, name: string): Row {
  return { id, tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", unit_id: unit, code, name, state: "draft", row_version: 3,
    cancellation_reason: "",
    completed_by_user_id: null, completed_at: null, cancelled_by_user_id: null, cancelled_at: null,
    created_by_user_id: actorId, created_at: "2026-11-12T12:00:00Z", updated_at: "2026-11-12T12:00:00Z" };
}
function program(id = programA, unit = unitA, code = "AP-A", name = "Annual assurance programme"): Row {
  return { ...base(id, unit, code, name), objective: "Evaluate the effectiveness of controlled operations.", description: "Synthetic risk-based planning record.", date_start: "2027-01-01", date_end: "2027-12-31", owner_user_id: memberA, approved_by_user_id: null, approved_at: null };
}
function audit(id = auditA, unit = unitA, code = "IA-A", name = "Receiving process audit"): Row {
  return { ...base(id, unit, code, name), program_id: unit === unitA ? programA : programB,
    audit_type: "process", planned_start: "2027-03-01", planned_end: "2027-03-03",
    objective: "Review receiving process controls.", scope_summary: "Receiving and material inspection.", conclusion: "",
    lead_auditor_user_id: memberA, actual_start: null, actual_end: null,
    independence_status: "pending", independence_notes: "", independence_reviewed_by_user_id: null, independence_reviewed_at: null };
}
async function fixture(page: Page, assigned = capabilities) {
  await authenticateWithKeycloak(page, { username: "pmc-user-a", password: String(password) });
  const state: FixtureState = {
    capabilities: [...assigned], programs: [program(), program(programB, unitB, "AP-B", "Supplier assurance programme")],
    audits: [audit(), audit(auditB, unitB, "IA-B", "Supplier process audit")], writeStatus: null,
    conflict: false, hold: false, reads: [], writes: [], unexpectedWrites: [], scopes: [], scopeMismatch: false, criteria: [], criterionMismatch: false,
  };
  fixtures.set(page, state);
  let markPending = () => {}; let release = () => {}; let markSettled = () => {};
  const pending = new Promise<void>((resolve) => { markPending = resolve; });
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const settled = new Promise<void>((resolve) => { markSettled = resolve; });
  await page.route("**/api/identity/**", async (route) => {
    const request = route.request(); const url = new URL(request.url());
    const path = url.pathname.replace("/api/identity", ""); const method = request.method();
    const endpoint = path.match(/^\/internal-audits\/(programs|audits)(?:\/([0-9a-f-]+)(\/transition)?)?$/i);
    const criterionEndpoint = path.match(/^\/internal-audits\/audits\/([0-9a-f-]+)\/criteria(?:\/([0-9a-f-]+)(\/withdraw)?)?$/i);
    if (method !== "GET" && criterionEndpoint) {
      if (!((method === "POST" && (!criterionEndpoint[2] || criterionEndpoint[3])) || (method === "PATCH" && criterionEndpoint[2] && !criterionEndpoint[3]))) {
        state.unexpectedWrites.push(`${method} ${path}`); return route.abort("blockedbyclient");
      }
      const body = request.postDataJSON() as Record<string, unknown>;
      state.writes.push({ method, path, body });
      const parent = state.audits.find(row => row.id === criterionEndpoint[1]);
      const current = state.criteria.find(row => row.id === criterionEndpoint[2]);
      const status = state.writeStatus ?? (criterionEndpoint[2] ? 200 : 201);
      if (status === 403) state.capabilities = [];
      if (status === 409 && state.conflict && parent) parent.row_version += 1;
      if (status < 200 || status >= 300 || status === 202) return route.fulfill({ status, json: { detail: "Synthetic criterion feedback" } });
      if (!parent) return route.fulfill({ status: 404, json: { detail: "Missing parent" } });
      const changes = { ...body }; delete changes.expected_version; delete changes.expected_audit_version;
      const result: CriterionRow = current ? { ...current, ...(criterionEndpoint[3] ? { status: "withdrawn", withdrawal_reason: String(body.reason) } : changes), row_version: current.row_version + 1 } : {
        id: createdId, audit_id: parent.id, unit_id: parent.unit_id, sequence: Number(body.sequence), title: String(body.title), requirement: String(body.requirement), source_type: String(body.source_type), reference: String(body.reference), scope_id: body.scope_id as string | null, status: "active", row_version: 1, withdrawal_reason: "",
      };
      if (current) state.criteria[state.criteria.indexOf(current)] = result; else state.criteria.push(result);
      parent.row_version += 1;
      return route.fulfill({ status, json: { criterion: result, audit_version: parent.row_version } });
    }
    const scopeEndpoint = path.match(/^\/internal-audits\/audits\/([0-9a-f-]+)\/scopes(?:\/([0-9a-f-]+)(\/withdraw)?)?$/i);
    if (method !== "GET" && scopeEndpoint) {
      if (!((method === "POST" && (!scopeEndpoint[2] || scopeEndpoint[3])) || (method === "PATCH" && scopeEndpoint[2] && !scopeEndpoint[3]))) {
        state.unexpectedWrites.push(`${method} ${path}`); return route.abort("blockedbyclient");
      }
      const body = request.postDataJSON() as Record<string, unknown>;
      state.writes.push({ method, path, body });
      const parent = state.audits.find(row => row.id === scopeEndpoint[1]);
      const current = state.scopes.find(row => row.id === scopeEndpoint[2]);
      const status = state.writeStatus ?? (scopeEndpoint[2] ? 200 : 201);
      if (status === 403) state.capabilities = [];
      if (status === 409 && state.conflict && parent) parent.row_version += 1;
      if (status < 200 || status >= 300 || status === 202) return route.fulfill({ status, json: { detail: "Synthetic scope feedback" } });
      if (!parent) return route.fulfill({ status: 404, json: { detail: "Missing parent" } });
      const changes = { ...body }; delete changes.expected_version; delete changes.expected_audit_version;
      const result: ScopeRow = current ? { ...current, ...(scopeEndpoint[3] ? { status: "withdrawn", withdrawal_reason: String(body.reason) } : changes), row_version: current.row_version + 1 } : {
        id: createdId, audit_id: parent.id, unit_id: parent.unit_id, sequence: Number(body.sequence), title: String(body.title), description: String(body.description), process_id: body.process_id as string | null, status: "active", row_version: 1, withdrawal_reason: "",
      };
      if (current) state.scopes[state.scopes.indexOf(current)] = result; else state.scopes.push(result);
      parent.row_version += 1;
      return route.fulfill({ status, json: { scope: result, audit_version: parent.row_version } });
    }
    if (method !== "GET") {
      const permitted = endpoint && ((method === "POST" && (!endpoint[2] || endpoint[3])) || (method === "PATCH" && endpoint[2] && !endpoint[3]));
      if (!permitted) { state.unexpectedWrites.push(`${method} ${path}`); return route.abort("blockedbyclient"); }
      const body = request.postDataJSON() as Record<string, unknown>;
      state.writes.push({ method, path, body });
      const kind = endpoint[1] as Kind; const rows = state[kind];
      const current = rows.find((row) => row.id === endpoint[2]);
      const status = state.writeStatus ?? (endpoint[2] ? 200 : 201);
      if (status === 403) state.capabilities = [];
      if (status === 409 && state.conflict && current) { current.row_version += 1; current.name = "Concurrent reviewed planning title"; }
      if (status < 200 || status >= 300) return route.fulfill({ status, json: { detail: "Synthetic command feedback" } });
      if (status === 202) return route.fulfill({ status, json: { detail: "Unconfirmed synthetic result" } });
      let result: Row;
      if (!endpoint[2]) {
        result = { ...(kind === "programs" ? program(createdId) : audit(createdId)), ...body, id: createdId, row_version: 1 };
        rows.unshift(result);
      } else if (current && endpoint[3]) {
        current.state = String(body.target_state); current.row_version += 1;
        if (current.state === "approved") { current.approved_by_user_id = actorId; current.approved_at = "2026-11-12T12:01:00Z"; }
        if (current.state === "completed") { current.completed_by_user_id = actorId; current.completed_at = "2026-11-12T12:03:00Z"; }
        if (current.state === "cancelled") { current.cancellation_reason = String(body.decision); current.cancelled_by_user_id = actorId; current.cancelled_at = "2026-11-12T12:04:00Z"; }
        result = current;
      } else if (current) {
        const changes = { ...body }; delete changes.expected_version;
        result = { ...current, ...changes, row_version: current.row_version + 1 };
        rows[rows.indexOf(current)] = result;
      } else return route.fulfill({ status: 404, json: { detail: "Synthetic target missing" } });
      return route.fulfill({ status, json: result });
    }
    state.reads.push({ path, query: Object.fromEntries(url.searchParams) });
    const unit = url.searchParams.get("unit_id") ?? unitA;
    const offset = Number(url.searchParams.get("offset") ?? 0); const limit = Number(url.searchParams.get("limit") ?? 50);
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    let body: unknown;
    if (path === "/qms-access/active-capabilities") body = { capabilities };
    else if (path === "/qms-access/effective") body = { unit_id: unit, capabilities: state.capabilities };
    else if (path === "/organization/units") body = [
      { id: unitA, code: "PLAN-A", name: "Planning scope A", status: "active" },
      { id: unitB, code: "PLAN-B", name: "Planning scope B", status: "active" },
    ];
    else if (path === "/organization/members") {
      body = Array.from({ length: 55 }, (_, index) => ({
        id: index === 0 ? memberA : `80000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
        display_name: index === 0 ? "Ana Quality" : `Planning person ${index + 1}`,
        role: "member", status: "active",
      })).filter((member) => member.display_name.toLowerCase().includes(q)).slice(offset, offset + limit);
    } else if (criterionEndpoint) {
      body = state.criteria.filter(row => row.audit_id === criterionEndpoint[1] && row.status === url.searchParams.get("status")).slice(offset, offset + limit).map(row => state.criterionMismatch ? { ...row, unit_id: unitB } : row);
    } else if (scopeEndpoint) {
      body = state.scopes.filter(row => row.audit_id === scopeEndpoint[1] && row.status === url.searchParams.get("status")).slice(offset, offset + limit).map(row => state.scopeMismatch ? { ...row, unit_id: unitB } : row);
    } else if (path === "/processes") {
      const search = (url.searchParams.get("search") ?? "").toLowerCase();
      body = Array.from({ length: 25 }, (_, index) => ({ id: `b0000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, unit_id: unit, code: `PROC-${index + 1}`, name: `Process ${index + 1}`, status: "active" })).filter(row => row.name.toLowerCase().includes(search)).slice(offset, offset + limit);
    }
    else if (endpoint) {
      const kind = endpoint[1] as Kind;
      if (endpoint[2]) {
        const row = state[kind].find((row) => row.id === endpoint[2]);
        return row ? route.fulfill({ status: 200, json: row }) : route.fulfill({ status: 404, json: { detail: "Synthetic record missing" } });
      }
      const rows = state[kind].filter((row) => row.unit_id === unit && (!q || `${row.code} ${row.name}`.toLowerCase().includes(q)));
      body = rows.slice(offset, offset + limit);
      if (state.hold && kind === "programs" && unit === unitA) {
        markPending(); await gate;
        try { await route.fulfill({ status: 200, json: body }); }
        catch (cause) { if (!request.failure()) throw cause; }
        finally { markSettled(); }
        return;
      }
    } else return route.fallback();
    return route.fulfill({ status: 200, json: body });
  });
  await page.goto("/#internal-audits-heading", { waitUntil: "networkidle" });
  await page.reload({ waitUntil: "networkidle" });
  await page.getByRole("link", { name: "Internal audits", exact: true }).click();
  const panel = page.locator('section[aria-labelledby="internal-audits-heading"]');
  await expect(panel.getByRole("heading", { name: "Internal audits", exact: true })).toBeVisible();
  return { state, panel, pending, release: async () => { release(); await settled; await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))); } };
}
async function tab(panel: Locator, name: "Programs" | "Scheduled audits") {
  await panel.getByRole("tab", { name, exact: true }).click();
  await expect(panel.getByRole("tab", { name, exact: true })).toHaveAttribute("aria-selected", "true");
}
async function programDraft(panel: Locator) {
  await panel.getByRole("button", { name: "New program", exact: true }).click();
  const form = panel.getByRole("form", { name: "Create audit program", exact: true });
  await form.getByLabel("Code", { exact: true }).fill("AP-NEW");
  await form.getByLabel("Title", { exact: true }).fill("New annual audit programme");
  await form.getByLabel("Objective", { exact: true }).fill("Assess controlled operations.");
  await form.getByLabel("Description", { exact: true }).fill("Synthetic annual plan.");
  await form.getByLabel("Starts on", { exact: true }).fill("2027-01-01");
  await form.getByLabel("Ends on", { exact: true }).fill("2027-12-31");
  return form;
}
async function auditDraft(panel: Locator) {
  await tab(panel, "Scheduled audits");
  await panel.getByRole("button", { name: "New audit", exact: true }).click();
  const form = panel.getByRole("form", { name: "Create internal audit", exact: true });
  await form.getByLabel("Code", { exact: true }).fill("IA-NEW");
  await form.getByLabel("Title", { exact: true }).fill("New receiving audit");
  await form.getByLabel("Objective", { exact: true }).fill("Assess receiving controls.");
  await form.getByLabel("Audit type", { exact: true }).selectOption("process");
  await form.getByLabel("Planned start", { exact: true }).fill("2027-03-01");
  await form.getByLabel("Planned end", { exact: true }).fill("2027-03-03");
  await form.getByLabel("Scope summary", { exact: true }).fill("Receiving and inspection.");
  return form;
}
function onlyFields(body: Record<string, unknown>, allowed: string[]) {
  expect(Object.keys(body).filter((key) => !allowed.includes(key)), "Do not invent API fields").toEqual([]);
}

test.describe("internal-audit planning fixtures (all QMS writes intercepted)", () => {
  test.beforeEach(() => test.skip(!password, "Synthetic development credential was not provided"));

  test("planning records remain distinct from execution and technical audit trail", async ({ page }) => {
    const { state, panel } = await fixture(page, ["audits.read"]);
    await expect(panel.getByRole("heading", { name: "Annual assurance programme", exact: true })).toBeVisible();
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("heading", { name: "Receiving process audit", exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: /Start execution|Complete audit|Confirm independence|Record finding/i })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "New audit", exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("creating a programme sends only its existing contract", async ({ page }) => {
    const { state, panel } = await fixture(page);
    const form = await programDraft(panel);
    await form.getByLabel("Responsible person (optional)", { exact: true }).selectOption(memberA);
    await form.getByRole("button", { name: "Create program", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes).toEqual([{ method: "POST", path: "/internal-audits/programs", body: {
      unit_id: unitA, code: "AP-NEW", name: "New annual audit programme", objective: "Assess controlled operations.",
      description: "Synthetic annual plan.", date_start: "2027-01-01", date_end: "2027-12-31", owner_user_id: memberA,
    } }]);
    await expect(panel.getByRole("heading", { name: "New annual audit programme", exact: true })).toBeVisible();
  });

  test("programme editing preserves the immutable identity and sends the current version", async ({ page }) => {
    const { state, panel } = await fixture(page);
    await panel.getByRole("button", { name: "Edit planning details", exact: true }).click();
    const form = panel.getByRole("form", { name: "Edit audit program", exact: true });
    await expect(form.getByLabel("Code", { exact: true })).toHaveCount(0);
    await form.getByLabel("Title", { exact: true }).fill("Updated assurance programme");
    await form.getByRole("button", { name: "Save planning details", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes).toHaveLength(1);
    expect(state.writes[0]).toMatchObject({ method: "PATCH", path: `/internal-audits/programs/${programA}`, body: { expected_version: 3, name: "Updated assurance programme", owner_user_id: memberA } });
    onlyFields(state.writes[0].body, ["expected_version", "name", "objective", "description", "date_start", "date_end", "owner_user_id"]);
  });

  test("creating an audit preserves the chosen programme and lead without execution metadata", async ({ page }) => {
    const { state, panel } = await fixture(page);
    const form = await auditDraft(panel);
    await form.getByLabel("Program (optional)", { exact: true }).selectOption(programA);
    await form.getByLabel("Lead auditor (optional)", { exact: true }).selectOption(memberA);
    await form.getByRole("button", { name: "Create audit", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes).toHaveLength(1);
    expect(state.writes[0]).toMatchObject({ method: "POST", path: "/internal-audits/audits", body: { unit_id: unitA, program_id: programA, code: "IA-NEW", name: "New receiving audit", audit_type: "process", planned_start: "2027-03-01", planned_end: "2027-03-03", objective: "Assess receiving controls.", scope_summary: "Receiving and inspection.", lead_auditor_user_id: memberA } });
    onlyFields(state.writes[0].body, ["unit_id", "program_id", "code", "name", "audit_type", "planned_start", "planned_end", "objective", "scope_summary", "conclusion", "lead_auditor_user_id"]);
    await expect(panel.getByRole("heading", { name: "New receiving audit", exact: true })).toBeVisible();
  });

  test("audit editing can clear nullable references without changing code or scope", async ({ page }) => {
    const { state, panel } = await fixture(page);
    await tab(panel, "Scheduled audits");
    await panel.getByRole("button", { name: "Edit planning details", exact: true }).click();
    const form = panel.getByRole("form", { name: "Edit internal audit", exact: true });
    await form.getByLabel("Title", { exact: true }).fill("Updated receiving audit");
    await form.getByLabel("Program (optional)", { exact: true }).selectOption("");
    await form.getByLabel("Lead auditor (optional)", { exact: true }).selectOption("");
    await form.getByRole("button", { name: "Save planning details", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes).toHaveLength(1);
    expect(state.writes[0]).toMatchObject({ method: "PATCH", path: `/internal-audits/audits/${auditA}`, body: { expected_version: 3, name: "Updated receiving audit", program_id: null, lead_auditor_user_id: null } });
    onlyFields(state.writes[0].body, ["expected_version", "program_id", "name", "audit_type", "planned_start", "planned_end", "objective", "scope_summary", "conclusion", "lead_auditor_user_id"]);
  });

  test("review authority advances the programme lifecycle with a versioned decision", async ({ page }) => {
    const { state, panel } = await fixture(page, ["audits.read", "audits.review"]);
    await expect(panel.getByRole("button", { name: "Edit planning details", exact: true })).toHaveCount(0);
    for (const [action, version, destination] of [["Approve program", 3, "approved"], ["Activate program", 4, "active"], ["Complete program", 5, "completed"]] as const) {
      await panel.getByRole("button", { name: action, exact: true }).click();
      const form = panel.getByRole("form", { name: `${action} AP-A`, exact: true });
      await form.getByLabel("Decision", { exact: true }).fill(`Controlled decision ${destination}`);
      await form.getByRole("button", { name: `Confirm ${action.toLowerCase()}`, exact: true }).click();
      await expect(form).toHaveCount(0);
      expect(state.writes.at(-1)).toEqual({ method: "POST", path: `/internal-audits/programs/${programA}/transition`, body: { expected_version: version, target_state: destination, decision: `Controlled decision ${destination}` } });
    }
    await expect(panel.getByRole("button", { name: "Cancel program", exact: true })).toHaveCount(0);
    expect(state.writes).toHaveLength(3);
  });

  test("scheduling requires manage while cancellation requires review responsibility", async ({ page }) => {
    const { state, panel } = await fixture(page, ["audits.read", "audits.manage"]);
    await expect(panel.getByRole("button", { name: "Approve program", exact: true })).toHaveCount(0);
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("button", { name: "Cancel audit", exact: true })).toHaveCount(0);
    await panel.getByRole("button", { name: "Mark as planned", exact: true }).click();
    const form = panel.getByRole("form", { name: "Mark as planned IA-A", exact: true });
    await form.getByLabel("Decision", { exact: true }).fill("Dates confirmed for planning.");
    await form.getByRole("button", { name: "Confirm mark as planned", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes).toEqual([{ method: "POST", path: `/internal-audits/audits/${auditA}/transition`, body: { expected_version: 3, target_state: "planned", decision: "Dates confirmed for planning." } }]);
    state.capabilities = ["audits.read", "audits.review"];
    await panel.getByRole("button", { name: "Refresh planning workspace", exact: true }).click();
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("button", { name: "Cancel audit", exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: "Mark as planned", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Edit planning details", exact: true })).toHaveCount(0);
  });

  test("read-only responsibility exposes records without mutating controls", async ({ page }) => {
    const { state, panel } = await fixture(page, ["audits.read", "audits.execute"]);
    await expect(panel.getByRole("button", { name: "New program", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: /Approve program|Activate program|Cancel program|Edit planning details/ })).toHaveCount(0);
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("button", { name: /New audit|Mark as planned|Cancel audit|Edit planning details/ })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("temporary creation failure preserves the draft without an automatic retry", async ({ page }) => {
    const { state, panel } = await fixture(page); state.writeStatus = 503;
    const form = await programDraft(panel);
    await form.getByRole("button", { name: "Create program", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText("temporarily unavailable");
    await expect(form.getByLabel("Title", { exact: true })).toHaveValue("New annual audit programme");
    await expect(form.getByLabel("Code", { exact: true })).toHaveValue("AP-NEW");
    await expect(form.getByRole("button", { name: "Create program", exact: true })).toBeEnabled();
    await page.waitForLoadState("networkidle"); expect(state.writes).toHaveLength(1);
  });

  test("a version conflict requires explicit refresh without repeating its PATCH", async ({ page }) => {
    const { state, panel } = await fixture(page); state.writeStatus = 409; state.conflict = true;
    await panel.getByRole("button", { name: "Edit planning details", exact: true }).click();
    const form = panel.getByRole("form", { name: "Edit audit program", exact: true });
    await form.getByLabel("Title", { exact: true }).fill("Stale proposed title");
    await form.getByRole("button", { name: "Save planning details", exact: true }).click();
    await expect(panel.getByRole("alert")).toBeVisible();
    await expect(form.getByRole("button", { name: "Save planning details", exact: true })).toBeDisabled();
    await panel.getByRole("button", { name: "Refresh planning workspace", exact: true }).click();
    await expect(panel.getByRole("heading", { name: "Concurrent reviewed planning title", exact: true })).toBeVisible();
    expect(state.writes).toHaveLength(1); expect(state.writes[0].body.expected_version).toBe(3);
  });

  test("permission denial clears the draft and locally cached planning authority", async ({ page }) => {
    const { state, panel } = await fixture(page); state.writeStatus = 403;
    const form = await programDraft(panel);
    await form.getByRole("button", { name: "Create program", exact: true }).click();
    await expect(form).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "New program", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("heading", { name: "Annual assurance programme", exact: true })).toHaveCount(0);
    expect(state.writes).toHaveLength(1);
  });

  test("a response from the old unit cannot repopulate the new scope", async ({ page }) => {
    const { state, panel, pending, release } = await fixture(page); state.hold = true;
    await panel.getByRole("button", { name: "Refresh planning workspace", exact: true }).click(); await pending;
    await panel.getByRole("combobox", { name: "Organization scope", exact: true }).selectOption(unitB);
    await expect(panel.getByRole("heading", { name: "Supplier assurance programme", exact: true })).toBeVisible();
    await release();
    await expect(panel.getByRole("heading", { name: "Annual assurance programme", exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("programme and audit pagination use the existing scoped server contracts", async ({ page }) => {
    const { state, panel } = await fixture(page);
    state.programs = Array.from({ length: 21 }, (_, index) => program(`90000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, unitA, `AP-${index + 1}`, `Programme ${index + 1}`));
    state.audits = Array.from({ length: 21 }, (_, index) => ({ ...audit(`a0000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, unitA, `IA-${index + 1}`, `Scheduled audit ${index + 1}`), program_id: state.programs[0].id }));
    await panel.getByRole("button", { name: "Refresh planning workspace", exact: true }).click();
    for (const [mode, kind, title] of [["Programs", "programs", "Programme 21"], ["Scheduled audits", "audits", "Scheduled audit 21"]] as const) {
      await tab(panel, mode);
      const pages = panel.getByRole("navigation", { name: "Audit register pages", exact: true });
      await expect(panel.locator(".ncr-record-list > li")).toHaveCount(20);
      await pages.getByRole("button", { name: "Next", exact: true }).click();
      await expect(panel.getByRole("heading", { name: title, exact: true })).toBeVisible();
      expect(state.reads.some((read) => read.path === `/internal-audits/${kind}` && read.query.unit_id === unitA && read.query.offset === "20" && read.query.limit === "21")).toBe(true);
      await pages.getByRole("button", { name: "Previous", exact: true }).click();
      await expect(panel.locator(".ncr-record-list > li")).toHaveCount(20);
    }
    expect(state.writes).toEqual([]);
  });

  test("selected people survive reference searches that return another page", async ({ page }) => {
    const { state, panel } = await fixture(page);
    await panel.getByRole("button", { name: "Edit planning details", exact: true }).click();
    const form = panel.getByRole("form", { name: "Edit audit program", exact: true });
    const owner = form.getByLabel("Responsible person (optional)", { exact: true });
    await expect(owner).toHaveValue(memberA);
    await form.getByLabel("Find responsible person", { exact: true }).fill("Planning person 55");
    await form.getByRole("button", { name: "Search people", exact: true }).click();
    await expect(owner).toHaveValue(memberA);
    await expect(owner.locator(`option[value="${memberA}"]`)).toContainText("Ana Quality");
    expect(state.writes).toEqual([]);
  });

  test("a successful but unconfirmed response does not allow another blind creation", async ({ page }) => {
    const { state, panel } = await fixture(page); state.writeStatus = 202;
    const form = await programDraft(panel);
    await form.getByRole("button", { name: "Create program", exact: true }).click();
    await expect(panel.getByRole("alert")).toBeVisible();
    await expect(form.getByLabel("Code", { exact: true })).toHaveValue("AP-NEW");
    await expect(form.getByRole("button", { name: "Create program", exact: true })).toBeDisabled();
    expect(state.writes).toHaveLength(1);
  });

  test("planning forms support keyboard, mobile, desktop and both contrast themes", async ({ page }, testInfo) => {
    const { state, panel } = await fixture(page);
    const form = await auditDraft(panel);
    await form.getByLabel("Title", { exact: true }).press("Tab");
    expect(await page.locator(":focus").evaluate((element) => Boolean(element.closest("form")))).toBe(true);
    for (const width of [375, 1440]) for (const dark of [false, true]) {
      await page.setViewportSize({ width, height: 1000 });
      if (await page.getByRole("checkbox", { name: "Use dark theme", exact: true }).isChecked() !== dark) await page.locator("label.theme-switch").click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", dark ? "dark" : "light");
      await expect(form).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      const results = await new AxeBuilder({ page }).include('section[aria-labelledby="internal-audits-heading"]').withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(results.violations).toEqual([]);
      const screenshot = testInfo.outputPath(`planning-${width}-${dark ? "dark" : "light"}.png`);
      await panel.screenshot({ path: screenshot });
      await testInfo.attach(`planning-${width}-${dark ? "dark" : "light"}`, { path: screenshot, contentType: "image/png" });
    }
    expect(state.writes).toEqual([]);
  });
});


test("live seeded audit planning is persisted and readable", async ({ page }, testInfo) => {
  test.skip(!password, "Synthetic credential required");
  await authenticateWithKeycloak(page, { username: "pmc-user-a", password: String(password) });
  await page.goto("/#internal-audits-heading", { waitUntil: "networkidle" });
  const panel=page.locator('section[aria-labelledby="internal-audits-heading"]');
  const unit=panel.getByRole("combobox", {name:"Organization scope"});
  const option=unit.locator("option").filter({hasText:"DEV-ACCESS-UI"});
  await unit.selectOption(String(await option.getAttribute("value")));
  await expect(panel).toContainText("DEMO-AP-001");
  await tab(panel,"Scheduled audits");
  await expect(panel).toContainText("DEMO-AUD-001");
  await expect(panel).toContainText("Recepción y aceptación de materiales — demostración");
  await expect(panel).toContainText("Aceptación documentada de materiales — demostración");
  await expect(panel).toContainText("pending");
  const screenshot=testInfo.outputPath("live-audit-planning.png");
  await page.evaluate(() => window.scrollTo({top:0,behavior:"instant"}));
  await page.screenshot({path:screenshot,fullPage:true});
  await testInfo.attach("live-audit-planning",{path:screenshot,contentType:"image/png"});
});

function scopeRow(index = 1): ScopeRow {
  return { id: `c0000000-0000-4000-8000-${String(index).padStart(12, "0")}`, audit_id: auditA, unit_id: unitA, sequence: index, title: `Receiving scope ${index}`, description: "Inspect controlled receiving records.", process_id: null, status: "active", row_version: 1, withdrawal_reason: "" };
}
async function scopeDraft(panel: Locator) {
  await panel.getByRole("button", { name: "Add scope item", exact: true }).click();
  const form = panel.getByRole("form", { name: "Add audit scope", exact: true });
  await form.getByLabel("Scope order", { exact: true }).fill("10");
  await form.getByLabel("Scope title", { exact: true }).fill("Receiving and material inspection");
  await form.getByLabel("Scope description", { exact: true }).fill("Sample incoming material acceptance records.");
  return form;
}

test.describe("structured audit scope (mocked writes, real browser)", () => {
  test.beforeEach(() => test.skip(!password, "Synthetic development credential required"));

  test("scope creation, editing and withdrawal preserve versions and history", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits");
    const form = await scopeDraft(panel);
    await form.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes[0]).toEqual({ method: "POST", path: `/internal-audits/audits/${auditA}/scopes`, body: { expected_audit_version: 3, sequence: 10, title: "Receiving and material inspection", description: "Sample incoming material acceptance records.", process_id: null } });
    await panel.getByRole("button", { name: "Edit scope 10", exact: true }).click();
    const edit = panel.getByRole("form", { name: "Edit audit scope", exact: true });
    await edit.getByLabel("Scope title", { exact: true }).fill("Revised receiving scope");
    await edit.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(edit).toHaveCount(0);
    expect(state.writes[1]).toMatchObject({ method: "PATCH", body: { expected_audit_version: 4, expected_version: 1, title: "Revised receiving scope" } });
    await panel.getByRole("button", { name: "Withdraw scope 10", exact: true }).click();
    const withdraw = panel.getByRole("form", { name: "Withdraw audit scope", exact: true });
    await withdraw.getByLabel("Scope withdrawal reason", { exact: true }).fill("Superseded after planning review.");
    await withdraw.getByRole("button", { name: "Confirm scope withdrawal", exact: true }).click();
    await expect(withdraw).toHaveCount(0);
    expect(state.writes[2]).toEqual({ method: "POST", path: `/internal-audits/audits/${auditA}/scopes/${createdId}/withdraw`, body: { expected_audit_version: 5, expected_version: 2, reason: "Superseded after planning review." } });
    await panel.getByLabel("Scope history", { exact: true }).selectOption("withdrawn");
    await expect(panel).toContainText("Withdrawn: Superseded after planning review.");
    await expect(panel.getByRole("button", { name: "Edit scope 10", exact: true })).toHaveCount(0);
    expect(state.audits[0].row_version).toBe(6);
  });

  test("scope conflict locks replay until explicit parent reconciliation", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits");
    state.writeStatus = 409; state.conflict = true;
    const form = await scopeDraft(panel);
    await form.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(form.getByRole("button", { name: "Save audit scope", exact: true })).toBeDisabled();
    await expect(form.getByLabel("Scope title", { exact: true })).toHaveValue("Receiving and material inspection");
    expect(state.writes).toHaveLength(1);
    state.writeStatus = null;
    await panel.getByRole("button", { name: "Refresh audit scope", exact: true }).click();
    await expect(form).toHaveCount(0);
    const retry = await scopeDraft(panel);
    await retry.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(retry).toHaveCount(0);
    expect(state.writes).toHaveLength(2); expect(state.writes[1].body.expected_audit_version).toBe(4);
  });

  test("scope refresh also reconciles a cancelled parent state", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits");
    state.audits[0].state = "cancelled"; state.audits[0].row_version += 1;
    await panel.getByRole("button", { name: "Refresh audit scope", exact: true }).click();
    await expect(panel.getByRole("button", { name: "Add scope item", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Edit planning details", exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("temporary scope failure preserves the draft and sends only one command", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits"); state.writeStatus = 503;
    const form = await scopeDraft(panel);
    await form.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(panel.getByRole("alert")).toBeVisible();
    await expect(form.getByLabel("Scope title", { exact: true })).toHaveValue("Receiving and material inspection");
    await expect(form.getByRole("button", { name: "Save audit scope", exact: true })).toBeEnabled();
    expect(state.writes).toHaveLength(1);
  });

  test("unconfirmed scope success blocks duplicate creation", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits"); state.writeStatus = 202;
    const form = await scopeDraft(panel);
    await form.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(form.getByRole("button", { name: "Save audit scope", exact: true })).toBeDisabled();
    await expect(form.getByLabel("Scope title", { exact: true })).toHaveValue("Receiving and material inspection");
    expect(state.writes).toHaveLength(1);
  });

  test("scope denial closes the entire cached audit context", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits"); state.writeStatus = 403;
    const form = await scopeDraft(panel);
    await form.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(form).toHaveCount(0);
    await expect(panel.getByRole("heading", { name: "Receiving process audit", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Add scope item", exact: true })).toHaveCount(0);
    expect(state.writes).toHaveLength(1);
  });

  test("read-only users can inspect paginated history without scope controls", async ({ page }) => {
    const { state, panel } = await fixture(page, ["audits.read"]);
    state.scopes = Array.from({ length: 21 }, (_, index) => scopeRow(index + 1));
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("button", { name: "Add scope item", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: /^Edit scope|^Withdraw scope/ })).toHaveCount(0);
    await panel.getByRole("button", { name: "More scope", exact: true }).click();
    await expect(panel).toContainText("21 · Receiving scope 21");
    expect(state.reads.some(row => row.path.endsWith("/scopes") && row.query.offset === "20" && row.query.limit === "21" && row.query.status === "active")).toBe(true);
    expect(state.writes).toEqual([]);
  });

  test("scope from another unit is rejected rather than displayed", async ({ page }) => {
    const { state, panel } = await fixture(page); state.scopes = [scopeRow()]; state.scopeMismatch = true;
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("alert")).toBeVisible();
    await expect(panel.getByText("1 · Receiving scope 1", { exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("selected process survives paginated searches and uses the scoped contract", async ({ page }) => {
    const { state, panel } = await fixture(page, [...capabilities, "processes.read"]); await tab(panel, "Scheduled audits");
    const form = await scopeDraft(panel);
    const process = form.getByLabel("Scope process (optional)", { exact: true });
    const selected = "b0000000-0000-4000-8000-000000000001";
    await expect(process).toBeEnabled(); await process.selectOption(selected);
    await form.getByLabel("Find scope process", { exact: true }).fill("Process 25");
    await form.getByRole("button", { name: "Search scope processes", exact: true }).click();
    await expect(process.locator("option").filter({ hasText: "PROC-25" })).toHaveCount(1);
    await expect(process).toHaveValue(selected);
    await expect(process.locator(`option[value="${selected}"]`)).toContainText("PROC-1 · Process 1");
    await form.getByRole("button", { name: "Save audit scope", exact: true }).click();
    await expect(form).toHaveCount(0); expect(state.writes[0].body.process_id).toBe(selected);
    expect(state.reads.some(row => row.path === "/processes" && row.query.unit_id === unitA && row.query.search === "Process 25" && !("q" in row.query))).toBe(true);
  });

  test("scope forms reflow and pass axe in both themes", async ({ page }, testInfo) => {
    const { panel } = await fixture(page, [...capabilities, "processes.read"]); await tab(panel, "Scheduled audits");
    const form = await scopeDraft(panel);
    await expect(form.getByLabel("Scope process (optional)", { exact: true })).toBeEnabled();
    for (const width of [375, 1440]) for (const dark of [false, true]) {
      await page.setViewportSize({ width, height: 1000 });
      if (await page.getByRole("checkbox", { name: "Use dark theme", exact: true }).isChecked() !== dark) await page.locator("label.theme-switch").click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", dark ? "dark" : "light");
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      const results = await new AxeBuilder({ page }).include('section[aria-labelledby="internal-audits-heading"]').withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(results.violations).toEqual([]);
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
      const screenshot = testInfo.outputPath(`scope-${width}-${dark ? "dark" : "light"}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      await testInfo.attach(`scope-${width}-${dark ? "dark" : "light"}`, { path: screenshot, contentType: "image/png" });
    }
  });
});


function criterionRow(index = 1): CriterionRow {
  return { id: `c0000000-0000-4000-8000-${String(index).padStart(12, "0")}`, audit_id: auditA, unit_id: unitA, sequence: index, title: `Receiving criterion ${index}`, requirement: "Inspect controlled receiving records.", source_type: "internal", reference: "PROC-RCV v1", scope_id: null, status: "active", row_version: 1, withdrawal_reason: "" };
}
async function criterionDraft(panel: Locator) {
  await panel.getByRole("button", { name: "Add criterion", exact: true }).click();
  const form = panel.getByRole("form", { name: "Add audit criterion", exact: true });
  await form.getByLabel("Criterion order", { exact: true }).fill("10");
  await form.getByLabel("Criterion title", { exact: true }).fill("Receiving and material inspection");
  await form.getByLabel("Requirement", { exact: true }).fill("Sample incoming material acceptance records.");
  await form.getByLabel("Source type", { exact: true }).selectOption("internal");
  await form.getByLabel("Source reference", { exact: true }).fill("PROC-RCV v1");
  return form;
}

test.describe("audit criteria (mocked writes, real browser)", () => {
  test.beforeEach(() => test.skip(!password, "Synthetic development credential required"));

  test("criterion creation, editing and withdrawal preserve versions and history", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits");
    const form = await criterionDraft(panel);
    await form.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(form).toHaveCount(0);
    expect(state.writes[0]).toEqual({ method: "POST", path: `/internal-audits/audits/${auditA}/criteria`, body: { expected_audit_version: 3, sequence: 10, title: "Receiving and material inspection", requirement: "Sample incoming material acceptance records.", source_type: "internal", reference: "PROC-RCV v1", scope_id: null } });
    await panel.getByRole("button", { name: "Edit criterion 10", exact: true }).click();
    const edit = panel.getByRole("form", { name: "Edit audit criterion", exact: true });
    await edit.getByLabel("Criterion title", { exact: true }).fill("Revised receiving scope");
    await edit.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(edit).toHaveCount(0);
    expect(state.writes[1]).toMatchObject({ method: "PATCH", body: { expected_audit_version: 4, expected_version: 1, title: "Revised receiving scope" } });
    await panel.getByRole("button", { name: "Withdraw criterion 10", exact: true }).click();
    const withdraw = panel.getByRole("form", { name: "Withdraw audit criterion", exact: true });
    await withdraw.getByLabel("Criterion withdrawal reason", { exact: true }).fill("Superseded after planning review.");
    await withdraw.getByRole("button", { name: "Confirm criterion withdrawal", exact: true }).click();
    await expect(withdraw).toHaveCount(0);
    expect(state.writes[2]).toEqual({ method: "POST", path: `/internal-audits/audits/${auditA}/criteria/${createdId}/withdraw`, body: { expected_audit_version: 5, expected_version: 2, reason: "Superseded after planning review." } });
    await panel.getByLabel("Criterion history", { exact: true }).selectOption("withdrawn");
    await expect(panel).toContainText("Withdrawn: Superseded after planning review.");
    await expect(panel.getByRole("button", { name: "Edit criterion 10", exact: true })).toHaveCount(0);
    expect(state.audits[0].row_version).toBe(6);
  });

  test("criterion conflict locks replay until explicit parent reconciliation", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits");
    state.writeStatus = 409; state.conflict = true;
    const form = await criterionDraft(panel);
    await form.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(form.getByRole("button", { name: "Save audit criterion", exact: true })).toBeDisabled();
    await expect(form.getByLabel("Criterion title", { exact: true })).toHaveValue("Receiving and material inspection");
    expect(state.writes).toHaveLength(1);
    state.writeStatus = null;
    await panel.getByRole("button", { name: "Refresh audit criteria", exact: true }).click();
    await expect(form).toHaveCount(0);
    const retry = await criterionDraft(panel);
    await retry.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(retry).toHaveCount(0);
    expect(state.writes).toHaveLength(2); expect(state.writes[1].body.expected_audit_version).toBe(4);
  });

  test("criterion refresh also reconciles a cancelled parent state", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits");
    state.audits[0].state = "cancelled"; state.audits[0].row_version += 1;
    await panel.getByRole("button", { name: "Refresh audit criteria", exact: true }).click();
    await expect(panel.getByRole("button", { name: "Add criterion", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Edit planning details", exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("temporary criterion failure preserves the draft and sends only one command", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits"); state.writeStatus = 503;
    const form = await criterionDraft(panel);
    await form.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(panel.getByRole("alert")).toBeVisible();
    await expect(form.getByLabel("Criterion title", { exact: true })).toHaveValue("Receiving and material inspection");
    await expect(form.getByRole("button", { name: "Save audit criterion", exact: true })).toBeEnabled();
    expect(state.writes).toHaveLength(1);
  });

  test("unconfirmed criterion success blocks duplicate creation", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits"); state.writeStatus = 202;
    const form = await criterionDraft(panel);
    await form.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(form.getByRole("button", { name: "Save audit criterion", exact: true })).toBeDisabled();
    await expect(form.getByLabel("Criterion title", { exact: true })).toHaveValue("Receiving and material inspection");
    expect(state.writes).toHaveLength(1);
  });

  test("criterion denial closes the entire cached audit context", async ({ page }) => {
    const { state, panel } = await fixture(page); await tab(panel, "Scheduled audits"); state.writeStatus = 403;
    const form = await criterionDraft(panel);
    await form.getByRole("button", { name: "Save audit criterion", exact: true }).click();
    await expect(form).toHaveCount(0);
    await expect(panel.getByRole("heading", { name: "Receiving process audit", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Add criterion", exact: true })).toHaveCount(0);
    expect(state.writes).toHaveLength(1);
  });

  test("read-only users can inspect paginated history without criterion controls", async ({ page }) => {
    const { state, panel } = await fixture(page, ["audits.read"]);
    state.criteria = Array.from({ length: 21 }, (_, index) => criterionRow(index + 1));
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("button", { name: "Add criterion", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: /^Edit criterion|^Withdraw criterion/ })).toHaveCount(0);
    await panel.getByRole("button", { name: "More criteria", exact: true }).click();
    await expect(panel).toContainText("21 · Receiving criterion 21");
    expect(state.reads.some(row => row.path.endsWith("/criteria") && row.query.offset === "20" && row.query.limit === "21" && row.query.status === "active")).toBe(true);
    expect(state.writes).toEqual([]);
  });

  test("criterion from another unit is rejected rather than displayed", async ({ page }) => {
    const { state, panel } = await fixture(page); state.criteria = [criterionRow()]; state.criterionMismatch = true;
    await tab(panel, "Scheduled audits");
    await expect(panel.getByRole("alert")).toBeVisible();
    await expect(panel.getByText("1 · Receiving criterion 1", { exact: true })).toHaveCount(0);
    expect(state.writes).toEqual([]);
  });

  test("selected scope survives reference pagination and stays within its audit", async ({ page }) => {
    const { state, panel } = await fixture(page);
    state.scopes = Array.from({ length: 21 }, (_, index) => scopeRow(index+1));
    await tab(panel,"Scheduled audits");
    const form = await criterionDraft(panel);
    const selected = state.scopes[0].id;
    const scope = form.getByLabel("Applies to scope (optional)", {exact:true});
    await expect(scope).toBeEnabled(); await scope.selectOption(selected);
    await form.getByRole("button", {name:"More scope choices",exact:true}).click();
    await expect(scope.locator(`option[value="${state.scopes[20].id}"]`)).toHaveCount(1);
    await expect(scope).toHaveValue(selected);
    await expect(scope.locator(`option[value="${selected}"]`)).toContainText("Receiving scope 1");
    await form.getByRole("button", {name:"Save audit criterion",exact:true}).click();
    await expect(form).toHaveCount(0);expect(state.writes[0].body.scope_id).toBe(selected);
    expect(state.reads.some(row=>row.path===`/internal-audits/audits/${auditA}/scopes`&&row.query.status==="active"&&row.query.offset==="20"&&row.query.limit==="21")).toBe(true);
  });

  test("criterion forms reflow and pass axe in both themes", async ({ page }, testInfo) => {
    const { panel } = await fixture(page, [...capabilities, "processes.read"]); await tab(panel, "Scheduled audits");
    const form = await criterionDraft(panel);
    await expect(form.getByLabel("Applies to scope (optional)", { exact: true })).toBeEnabled();
    for (const width of [375, 1440]) for (const dark of [false, true]) {
      await page.setViewportSize({ width, height: 1000 });
      if (await page.getByRole("checkbox", { name: "Use dark theme", exact: true }).isChecked() !== dark) await page.locator("label.theme-switch").click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", dark ? "dark" : "light");
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
      const results = await new AxeBuilder({ page }).include('section[aria-labelledby="internal-audits-heading"]').withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      expect(results.violations).toEqual([]);
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
      const screenshot = testInfo.outputPath(`criterion-${width}-${dark ? "dark" : "light"}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      await testInfo.attach(`criterion-${width}-${dark ? "dark" : "light"}`, { path: screenshot, contentType: "image/png" });
    }
  });
});
