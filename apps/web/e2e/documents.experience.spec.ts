import { expect, test, type Locator, type Page } from "@playwright/test";

import { authenticateWithKeycloak } from "./support/auth";

const password = process.env.KEYCLOAK_USER_A_PASSWORD;

async function authenticate(page: Page) {
  await authenticateWithKeycloak(page, { username: "pmc-user-a", password: String(password) });
}

test("live document search and refresh preserve creation references", async ({ page }) => {
  test.skip(!password, "Synthetic development credential was not provided");
  await authenticate(page);
  await page.goto("/#documents-heading", { waitUntil: "networkidle" });
  const panel = page.locator(".documents-workspace");
  const unit = panel.getByRole("combobox", { name: "Organizational unit" });
  const demoUnit = unit.locator("option").filter({ hasText: "DEV-ACCESS-UI" });
  await expect(demoUnit).toHaveCount(1);
  await unit.selectOption(String(await demoUnit.getAttribute("value")));
  await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
  await panel.getByRole("textbox", { name: "Find by code or title" }).fill("DEMO-DOC-001");
  await panel.getByRole("button", { name: "Search", exact: true }).click();
  await expect(panel.locator(".document-list")).toContainText("DEMO-DOC-001");
  await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
  await panel.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
  await panel.getByRole("button", { name: "New document", exact: true }).click();
  await expect(panel.getByRole("combobox", { name: "Process", exact: true }).locator("option").filter({ hasText: "DEMO-PROC-001" })).toHaveCount(1);
  await expect(panel.getByRole("combobox", { name: "Document owner (optional)" }).locator("option")).not.toHaveCount(1);
  await panel.getByRole("button", { name: "Cancel", exact: true }).click();
});

const unitA = "11111111-1111-4111-8111-111111111111";
const unitB = "22222222-2222-4222-8222-222222222222";
const caps = ["documents.read", "documents.author", "documents.obsolete", "processes.read"];
const units = [
  { id: unitA, code: "UI-A", name: "UI fixture A", status: "active" },
  { id: unitB, code: "UI-B", name: "UI fixture B", status: "active" },
];

function fixtureDocument(unit: string, suffix: string) {
  return { id: `doc-${suffix}`, unit_id: unit, process_id: `process-${unit}`, code: `UI-DOC-${suffix}`, title: `Synthetic procedure ${suffix}`, document_type: "procedure", owner_user_id: null, status: "active", current_revision_id: null, row_version: 1, created_at: "2026-01-01T00:00:00Z" };
}

type FixtureFileState = "missing" | "rejected";
type DocumentFixtureState = {
  denied: boolean;
  failReferences: boolean;
  holdReferences: boolean;
  paged: boolean;
  withRevisions: boolean;
  revisionStatus: number;
  uploadStatus: number;
  createRevisionStatus: number;
  createDocumentStatus: number;
  fileStates: Record<string, FixtureFileState>;
  revisionVersions: Record<string, number>;
  revisionReads: Record<string, number>;
  mutations: Array<{ method: string; path: string; body: string | null; contentType: string }>;
  unexpectedMutations: string[];
};

const fixtureStates = new WeakMap<Page, DocumentFixtureState>();

test.afterEach(async ({ page }) => {
  const state = fixtureStates.get(page);
  if (state) expect(state.unexpectedMutations, "Document fixtures must never forward unexpected writes").toEqual([]);
});

function fixtureRevision(suffix: string, state: DocumentFixtureState) {
  return {
    id: `revision-${suffix}`, document_id: `doc-${suffix}`, revision: "R1", status: "draft",
    prepared_by_user_id: "fixture-author", prepared_by_display_name: "Synthetic preparer",
    reviewed_by_user_id: null, reviewed_by_display_name: null, approved_by_user_id: null,
    approved_by_display_name: null, change_summary: "Synthetic client feedback fixture",
    revision_date: "2026-01-01", effective_date: null, review_date: null,
    file_state: state.fileStates[`doc-${suffix}`] ?? "missing", file_sha256: null,
    file_size: null, row_version: state.revisionVersions[`doc-${suffix}`] ?? 1,
    created_at: "2026-01-01T00:00:00Z",
  };
}

async function fixtureWorkspace(page: Page, options: { withRevisions?: boolean } = {}) {
  await authenticate(page);
  const state: DocumentFixtureState = {
    denied: false, failReferences: false, holdReferences: false, paged: false,
    withRevisions: Boolean(options.withRevisions), revisionStatus: 200, uploadStatus: 503,
    createRevisionStatus: 503, createDocumentStatus: 503, fileStates: {}, revisionVersions: {},
    revisionReads: {}, mutations: [], unexpectedMutations: [],
  };
  fixtureStates.set(page, state);
  let release = () => {};
  let held = () => {};
  let settle = () => {};
  const pending = new Promise<void>((resolve) => { held = resolve; });
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const settled = new Promise<void>((resolve) => { settle = resolve; });
  await page.route("**/api/identity/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/identity", "");
    const method = route.request().method();
    if (method !== "GET") {
      if (path.startsWith("/documents")) {
        const upload = path.match(/^\/documents\/doc-(A[12])\/revisions\/revision-\1\/file$/);
        const revisionPost = /^\/documents\/doc-A[12]\/revisions$/.test(path);
        const commandPost = /^\/documents\/doc-(A[12])\/revisions\/revision-\1\/(submit|reject|approve|release)$/.test(path);
        const allowed = state.withRevisions && (
          (method === "PUT" && Boolean(upload)) ||
          (method === "POST" && (path === "/documents" || revisionPost || commandPost))
        );
        if (!allowed) {
          state.unexpectedMutations.push(`${method} ${path}`);
          await route.abort("blockedbyclient");
          return;
        }
        state.mutations.push({ method, path, body: route.request().postData(), contentType: route.request().headers()["content-type"] ?? "" });
        if (upload) {
          if (state.uploadStatus === 202) state.fileStates[`doc-${upload[1]}`] = "rejected";
          if (state.uploadStatus === 202 || state.uploadStatus === 409) state.revisionVersions[`doc-${upload[1]}`] = 2;
          return route.fulfill({ status: state.uploadStatus, json: state.uploadStatus === 202 ? { file_state: "rejected" } : { detail: "Synthetic upload feedback" } });
        }
        if (commandPost && state.createRevisionStatus === 409) state.revisionVersions[path.split("/")[2]] = 2;
        return route.fulfill({ status: path === "/documents" ? state.createDocumentStatus : state.createRevisionStatus, json: { detail: "Synthetic command feedback" } });
      }
      return route.fallback();
    }
    const unit = url.searchParams.get("unit_id") ?? unitA;
    let body: unknown;
    if (path === "/organization/units") body = units;
    else if (path === "/qms-access/effective") body = { unit_id: unit, capabilities: state.denied ? [] : state.withRevisions ? [...caps, "documents.review", "documents.approve", "documents.release"] : caps };
    else if (path === "/documents") {
      body = state.paged
        ? (url.searchParams.get("offset") === "50" ? [fixtureDocument(unit, "A51")] : Array.from({ length: 51 }, (_, index) => fixtureDocument(unit, `A${index + 1}`)))
        : unit === unitA ? [fixtureDocument(unitA, "A1"), fixtureDocument(unitA, "A2")] : [fixtureDocument(unitB, "B1")];
    }
    else if (path === "/documents/processes") {
      if (state.holdReferences && unit === unitA) {
        held(); await gate;
        try {
          await route.fulfill({ status: 200, json: [{ id: `process-${unitA}`, code: "PROCESS-A", name: "Late synthetic process" }] });
        } catch (cause) {
          if (!route.request().failure()) throw cause;
        } finally { settle(); }
        return;
      }
      if (state.failReferences) return route.fulfill({ status: 503, json: { detail: "Fixture service failure" } });
      body = url.searchParams.get("search") === "no-match" ? [] : [{ id: `process-${unit}`, code: unit === unitA ? "PROCESS-A" : "PROCESS-B", name: "Synthetic process" }];
    } else if (path === "/organization/members") body = [{ id: "member-fixture", display_name: "Synthetic document owner", role: "member" }];
    else if (/^\/documents\/doc-[A-Z]\d+\/revisions$/.test(path)) {
      const suffix = path.split("/")[2].slice(4);
      const documentId = `doc-${suffix}`;
      state.revisionReads[documentId] = (state.revisionReads[documentId] ?? 0) + 1;
      if (state.revisionStatus !== 200) return route.fulfill({ status: state.revisionStatus, json: { detail: "Synthetic revision access failure" } });
      body = state.withRevisions ? [fixtureRevision(suffix, state)] : [];
    }
    else return route.fallback();
    return route.fulfill({ status: 200, json: body });
  });
  await page.goto("/#documents-heading", { waitUntil: "networkidle" });
  const panel = page.locator(".documents-workspace");
  await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
  return { panel, state, pending, release: async () => {
    release(); await settled;
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  } };
}

test.describe("document read-state fixtures (no backend mutations)", () => {
  test.beforeEach(() => test.skip(!password, "Synthetic development credential was not provided"));

  test("an empty process search can be cancelled and creation reopened", async ({ page }) => {
    const { panel } = await fixtureWorkspace(page);
    await panel.getByRole("button", { name: "New document", exact: true }).click();
    await panel.getByRole("textbox", { name: "Find process" }).fill("no-match");
    await expect(panel.getByRole("combobox", { name: "Process", exact: true }).locator("option")).toHaveCount(1);
    await panel.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
    await panel.getByRole("button", { name: "New document", exact: true }).click();
    await expect(panel.getByRole("textbox", { name: "Find process" })).toHaveValue("");
    await expect(panel.getByRole("combobox", { name: "Process", exact: true }).locator("option").filter({ hasText: "PROCESS-A" })).toHaveCount(1);
  });

  test("reference failure disables creation and refresh recovers it", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page);
    state.failReferences = true;
    await panel.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText("Document creation references could not be loaded");
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeDisabled();
    state.failReferences = false;
    await panel.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
    await expect(panel.getByRole("alert")).toHaveCount(0);
  });

  test("register pagination reloads creation references on every page", async ({ page }, testInfo) => {
    const { panel, state } = await fixtureWorkspace(page);
    state.paged = true;
    await panel.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(panel.locator(".document-list li")).toHaveCount(50);
    const pages = panel.getByRole("navigation", { name: "Document register pages" });
    await pages.getByRole("button", { name: "Next", exact: true }).click();
    await expect(pages).toContainText("Showing 51–51");
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
    await pages.getByRole("button", { name: "Previous", exact: true }).click();
    await expect(pages).toContainText("Showing 1–50");
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
    await testInfo.attach("document-pagination-synthetic", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
  });

  test("late references cannot repopulate a different unit", async ({ page }) => {
    const { panel, state, pending, release } = await fixtureWorkspace(page);
    state.holdReferences = true;
    await panel.getByRole("button", { name: "Refresh", exact: true }).click();
    await pending;
    await panel.getByRole("combobox", { name: "Organizational unit" }).selectOption(unitB);
    await expect(panel.locator(".document-list")).toContainText("UI-DOC-B1");
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toBeEnabled();
    await release();
    await panel.getByRole("button", { name: "New document", exact: true }).click();
    await expect(panel.getByRole("combobox", { name: "Process", exact: true })).toContainText("PROCESS-B");
    await expect(panel.getByRole("combobox", { name: "Process", exact: true })).not.toContainText("PROCESS-A");
    await expect(panel.locator(".document-list")).not.toContainText("UI-DOC-A");
  });

  test("revoked capabilities clear records and pending creation references", async ({ page }) => {
    const { panel, state, pending, release } = await fixtureWorkspace(page);
    state.holdReferences = true;
    await panel.getByRole("button", { name: "Refresh", exact: true }).click();
    await pending;
    state.denied = true;
    await panel.getByRole("button", { name: "Refresh", exact: true }).click();
    await expect(panel).toContainText("No document responsibilities are assigned");
    await release();
    await expect(panel.locator(".document-list li")).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("combobox", { name: "Process", exact: true })).toHaveCount(0);
  });

  test("a document does not inherit another record's obsolete confirmation", async ({ page }) => {
    const { panel } = await fixtureWorkspace(page);
    await panel.getByRole("button", { name: "Obsolete", exact: true }).click();
    await expect(panel.getByRole("button", { name: "Confirm obsolete", exact: true })).toBeVisible();
    await panel.locator(".document-list").getByRole("button").filter({ hasText: "UI-DOC-A2" }).click();
    await expect(panel.getByRole("button", { name: "Confirm obsolete", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Obsolete", exact: true })).toBeVisible();
  });
});

// This byte payload exercises client feedback only. All document writes below are
// intercepted fixtures; no PDF validation, antivirus or backend write is claimed.
const syntheticPDF = {
  name: "synthetic-feedback.pdf",
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.4\n% Synthetic client error-handling fixture only\n"),
};

async function selectFixtureRevision(panel: Locator, suffix = "A2") {
  const record = panel.locator(".document-list").getByRole("button").filter({ hasText: `UI-DOC-${suffix}` });
  if (!(await record.getAttribute("class"))?.split(/\s+/).includes("selected")) await record.click();
  await expect(panel.locator(".document-detail .detail-heading .eyebrow")).toHaveText(`UI-DOC-${suffix}`);
  await expect(panel.locator(".revision-actions").getByText("Revision R1", { exact: true })).toBeVisible();
}

test.describe("document command-feedback fixtures (all document writes intercepted)", () => {
  test.beforeEach(() => test.skip(!password, "Synthetic development credential was not provided"));

  test("reselecting the current document preserves its loaded revision", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel, "A1");
    await expect(panel.locator('.upload-control input[type="file"]')).toHaveCount(1);
    const readsBefore = state.revisionReads["doc-A1"];
    await panel.locator(".document-list").getByRole("button").filter({ hasText: "UI-DOC-A1" }).click();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(panel.locator(".document-detail .detail-heading .eyebrow")).toHaveText("UI-DOC-A1");
    await expect(panel.locator(".revision-actions").getByText("Revision R1", { exact: true })).toBeVisible();
    await expect(panel.locator(".revision-table-scroll")).toContainText("R1");
    await expect(panel.locator('.upload-control input[type="file"]')).toHaveCount(1);
    expect(state.revisionReads["doc-A1"]).toBe(readsBefore);
    expect(state.mutations).toHaveLength(0);
  });

  for (const status of [401, 403]) {
    test(`upload${status} clears document context and actions`, async ({ page }) => {
      const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
      await selectFixtureRevision(panel);
      state.uploadStatus = status;
      await panel.locator('.upload-control input[type="file"]').setInputFiles(syntheticPDF);
      await expect(panel.getByRole("alert")).toContainText(status === 401 ? "session has expired" : "not permitted");
      await expect(panel.locator(".document-list li")).toHaveCount(0);
      await expect(panel.locator(".revision-actions")).toHaveCount(0);
      await expect(panel.getByRole("button", { name: "New document", exact: true })).toHaveCount(0);
      await expect(panel.getByRole("button", { name: "New revision", exact: true })).toHaveCount(0);
      await expect(panel.getByRole("button", { name: "Obsolete", exact: true })).toHaveCount(0);
      expect(state.mutations).toHaveLength(1);
      expect(state.mutations[0]).toMatchObject({ method: "PUT", path: "/documents/doc-A2/revisions/revision-A2/file" });
    });
  }

  test("revision GET403 clears the register and document authority", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel, "A1");
    state.revisionStatus = 403;
    await panel.locator(".document-list").getByRole("button").filter({ hasText: "UI-DOC-A2" }).click();
    await expect(panel.getByRole("alert")).toContainText("not permitted");
    await expect(panel.locator(".document-list li")).toHaveCount(0);
    await expect(panel.locator(".revision-actions")).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "New document", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "New revision", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Obsolete", exact: true })).toHaveCount(0);
    expect(state.revisionReads["doc-A2"]).toBeGreaterThan(0);
    expect(state.mutations).toHaveLength(0);
  });

  test("revision POST503 preserves the form and entered draft", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel);
    await panel.getByRole("button", { name: "New revision", exact: true }).click();
    await panel.getByRole("textbox", { name: "Revision code", exact: true }).fill("R-RETRY");
    await panel.getByRole("textbox", { name: "Change summary", exact: true }).fill("Keep this synthetic draft after the temporary failure.");
    await panel.getByRole("button", { name: "Create revision", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText("temporarily unavailable");
    await expect(panel.getByRole("heading", { name: "Prepare a revision", exact: true })).toBeVisible();
    await expect(panel.getByRole("textbox", { name: "Revision code", exact: true })).toHaveValue("R-RETRY");
    await expect(panel.getByRole("textbox", { name: "Change summary", exact: true })).toHaveValue("Keep this synthetic draft after the temporary failure.");
    await expect(panel.getByRole("button", { name: "Create revision", exact: true })).toBeEnabled();
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ method: "POST", path: "/documents/doc-A2/revisions" });
    expect(JSON.parse(state.mutations[0].body!)).toMatchObject({ revision: "R-RETRY", change_summary: "Keep this synthetic draft after the temporary failure." });
  });

  test("document POST503 preserves the entered registration", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await panel.getByRole("button", { name: "New document", exact: true }).click();
    await panel.getByRole("textbox", { name: "Code", exact: true }).fill("UI-RETRY-001");
    await panel.getByRole("textbox", { name: "Title", exact: true }).fill("Synthetic registration to preserve");
    await panel.getByRole("combobox", { name: "Process", exact: true }).selectOption(`process-${unitA}`);
    await panel.getByRole("button", { name: "Create document", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText("temporarily unavailable");
    await expect(panel.getByRole("heading", { name: "Register a controlled document", exact: true })).toBeVisible();
    await expect(panel.getByRole("textbox", { name: "Code", exact: true })).toHaveValue("UI-RETRY-001");
    await expect(panel.getByRole("textbox", { name: "Title", exact: true })).toHaveValue("Synthetic registration to preserve");
    await expect(panel.getByRole("combobox", { name: "Process", exact: true })).toHaveValue(`process-${unitA}`);
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ method: "POST", path: "/documents" });
    expect(JSON.parse(state.mutations[0].body!)).toMatchObject({ unit_id: unitA, process_id: `process-${unitA}`, code: "UI-RETRY-001" });
  });

  test("upload503 reports a temporary service problem and permits an explicit retry", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel);
    const file = panel.locator('.upload-control input[type="file"]');
    await file.setInputFiles(syntheticPDF);
    await expect(panel.getByRole("alert")).toContainText("temporarily unavailable");
    await expect(panel.getByRole("alert")).not.toContainText(/scanner|signatures/i);
    await expect(file).toBeEnabled();
    await expect(file).toHaveValue("");
    expect(state.mutations).toHaveLength(1);
    await file.setInputFiles(syntheticPDF);
    await expect.poll(() => state.mutations.length).toBe(2);
    await expect(file).toBeEnabled();
    await expect(panel.locator(".document-detail .detail-heading .eyebrow")).toHaveText("UI-DOC-A2");
    expect(state.mutations.every((mutation) => mutation.method === "PUT" && mutation.path === "/documents/doc-A2/revisions/revision-A2/file")).toBe(true);
  });

  test("upload409 reconciles the selected revision without repeating the upload", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel);
    const readsBefore = state.revisionReads["doc-A2"];
    state.uploadStatus = 409;
    await panel.locator('.upload-control input[type="file"]').setInputFiles(syntheticPDF);
    await expect(panel.getByRole("alert")).toContainText("changed");
    await expect.poll(() => state.revisionReads["doc-A2"]).toBeGreaterThan(readsBefore);
    await expect(panel.locator(".document-detail .detail-heading .eyebrow")).toHaveText("UI-DOC-A2");
    await expect(panel.locator(".revision-actions").getByText("Revision R1", { exact: true })).toBeVisible();
    expect(state.revisionVersions["doc-A2"]).toBe(2);
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ method: "PUT", path: "/documents/doc-A2/revisions/revision-A2/file", body: syntheticPDF.buffer.toString("utf8"), contentType: "application/pdf" });
  });

  test("versioned command409 reconciles its target without repeating the command", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel);
    const readsBefore = state.revisionReads["doc-A2"];
    state.createRevisionStatus = 409;
    await panel.getByRole("button", { name: "Submit for review", exact: true }).click();
    await expect(panel.getByRole("alert")).toContainText("changed");
    await expect.poll(() => state.revisionReads["doc-A2"]).toBeGreaterThan(readsBefore);
    await expect(panel.locator(".document-detail .detail-heading .eyebrow")).toHaveText("UI-DOC-A2");
    await expect(panel.locator(".revision-actions").getByText("Revision R1", { exact: true })).toBeVisible();
    expect(state.revisionVersions["doc-A2"]).toBe(2);
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ method: "POST", path: "/documents/doc-A2/revisions/revision-A2/submit" });
    expect(JSON.parse(state.mutations[0].body!)).toEqual({ expected_version: 1 });
  });

  test("upload202 rejected file remains unusable on the selected document", async ({ page }) => {
    const { panel, state } = await fixtureWorkspace(page, { withRevisions: true });
    await selectFixtureRevision(panel);
    const readsBefore = state.revisionReads["doc-A2"];
    state.uploadStatus = 202;
    await panel.locator('.upload-control input[type="file"]').setInputFiles(syntheticPDF);
    await expect.poll(() => state.revisionReads["doc-A2"]).toBeGreaterThan(readsBefore);
    await expect(panel.locator(".document-detail .detail-heading .eyebrow")).toHaveText("UI-DOC-A2");
    await expect(panel.locator(".revision-actions").getByText("Revision R1", { exact: true })).toBeVisible();
    await expect(panel.locator(".revision-table-scroll")).toContainText("rejected");
    await expect(panel.getByRole("link", { name: "Download PDF", exact: true })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
    await expect(panel.locator('.upload-control input[type="file"]')).toHaveCount(0);
    expect(state.mutations).toHaveLength(1);
    expect(state.mutations[0]).toMatchObject({ method: "PUT", path: "/documents/doc-A2/revisions/revision-A2/file" });
  });
});
