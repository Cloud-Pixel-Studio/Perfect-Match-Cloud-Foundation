import { expect, test, type Page } from "@playwright/test";

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
  await panel.getByRole("combobox", { name: "Organizational unit" }).selectOption({ label: "Development access review · DEV-ACCESS-UI" });
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

async function fixtureWorkspace(page: Page) {
  await authenticate(page);
  const state = { denied: false, failReferences: false, holdReferences: false, paged: false };
  let release = () => {};
  let held = () => {};
  let settle = () => {};
  const pending = new Promise<void>((resolve) => { held = resolve; });
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const settled = new Promise<void>((resolve) => { settle = resolve; });
  await page.route("**/api/identity/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/identity", "");
    if (route.request().method() !== "GET") {
      if (path.startsWith("/documents")) throw new Error("UI fixtures must not mutate document records");
      return route.fallback();
    }
    const unit = url.searchParams.get("unit_id") ?? unitA;
    let body: unknown;
    if (path === "/organization/units") body = units;
    else if (path === "/qms-access/effective") body = { unit_id: unit, capabilities: state.denied ? [] : caps };
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
    else if (/^\/documents\/doc-[A-Z]\d+\/revisions$/.test(path)) body = [];
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
