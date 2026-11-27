import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import type { ContextFields, ContextRecord, PartyProcessLink, PartyRequirement } from "../src/lib/qms-context";

const tenant = "10000000-0000-4000-8000-000000000001";
const author = "20000000-0000-4000-8000-000000000001";
const reviewer = "20000000-0000-4000-8000-000000000002";
const firstUnit = "30000000-0000-4000-8000-000000000001";
const secondUnit = "30000000-0000-4000-8000-000000000002";
const recordId = "40000000-0000-4000-8000-000000000001";
const csrf = "synthetic-test-csrf-token";
const process = { id: "50000000-0000-4000-8000-000000000001", code: "RECV-01", name: "Receiving inspection", row_version: 7 };
const linkId = "60000000-0000-4000-8000-000000000001";
const purchaseRequirement: PartyRequirement = {
  id: "70000000-0000-4000-8000-000000000001", statement: "Match each received lot to its certificate.",
  source: "Purchasing requirement PR-12", disposition: "addressed_by_qms",
  rationale: "Receiving checks each lot before release.",
};
const seededParty: ContextRecord = {
  id: recordId, tenant_id: tenant, unit_id: firstUnit, kind: "interested-parties",
  code: "PARTY-01", name: "Synthetic component supplier", classification: "supplier",
  category: "", relevance: "relevant", description: "Traceable lots and timely documentation.",
  requirements: "", evidence_summary: "", owner_user_id: author, review_due_on: "2099-05-01",
  status: "active", row_version: 2, created_by_user_id: author, content_editor_user_id: author, updated_by_user_id: reviewer,
  updated_at: "2026-11-26T12:00:00Z", reviewed_at: "2026-11-26T12:00:00Z", decision_note: "Reviewed.",
  party_requirements: [purchaseRequirement], no_requirements_reason: "",
};

async function fixture(page: Page, withProcess = false) {
  let actor = author;
  let foreignPayload = false;
  let link: PartyProcessLink | null = null;
  let phases: Array<{ command: string; snapshot: ContextRecord }> = withProcess ? [{ command: "reviewed", snapshot: seededParty }] : [];
  const capabilities = () => [
    "context.read", actor === author ? "context.manage" : "context.review",
    ...(withProcess && actor === author ? ["processes.read"] : []),
  ];
  const units = [firstUnit, secondUnit].map((id, i) => ({
    id, tenant_id: tenant, code: `SITE-${i + 1}`, name: "Synthetic site", status: "active", unit_type: "site",
  }));
  await page.context().addCookies([{ name: "pm_csrf", value: csrf, domain: "127.0.0.1", path: "/" }]);
  await page.route("**/api/identity/**", async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/identity", "");
    const unit = url.searchParams.get("unit_id");
    const method = route.request().method();
    const ok = (json: unknown, status = 200) => route.fulfill({ json, status, headers: { "X-Tenant-ID": tenant } });
    if (path === "/auth/me") return ok({ id: actor, display_name: "Synthetic quality user", current_tenant_id: tenant, email: null });
    if (path === "/auth/tenants") return ok([{ id: tenant, name: "Synthetic tenant", slug: "synthetic", role: "member" }]);
    if (path === "/qms-access/active-capabilities") return ok({ capabilities: capabilities() });
    if (path === "/qms-access/effective") return ok({ unit_id: unit, capabilities: capabilities() });
    if (path === "/organization/units") return ok(units);
    if (path.startsWith("/organization/units/")) return ok(units.find(item => path.endsWith(item.id)));
    if (path === "/action-center") return ok({
      scope: "mine", generated_at: "2026-11-26T12:00:00Z",
      summary: { total: 0, overdue: 0, due_soon: 0, unassigned: 0, by_source: {} }, items: [],
    });
    if (path === "/context/members") return ok([{ user_id: reviewer, display_name: "Synthetic reviewer" }]);
    if (path === "/processes") return ok([]);
    if (path === "/context/issues") return ok([]);
    if (path === "/context/interested-parties" && method === "POST") {
      expect(route.request().headers()["x-csrf-token"]).toBe(csrf);
      const input = route.request().postDataJSON() as ContextFields & { unit_id: string };
      expect(input.unit_id).toBe(firstUnit);
      expect(input.party_requirements).toEqual([{
        id: expect.stringMatching(/^[\da-f-]{36}$/),
        statement: "Match each received lot to its certificate.",
        source: "Purchasing requirement PR-12",
        disposition: "addressed_by_qms",
        rationale: "Receiving checks each lot before release.",
      }]);
      const snapshot: ContextRecord = {
        ...input, kind: "interested-parties", id: recordId, tenant_id: tenant, status: "draft",
        row_version: 1, created_by_user_id: actor, content_editor_user_id: actor, updated_by_user_id: actor,
        updated_at: "2026-11-26T12:00:00Z", reviewed_at: null, decision_note: "",
        owner_display_name: "Synthetic quality user",
      };
      phases = [{ command: "created", snapshot }];
      return ok(snapshot, 201);
    }
    if (path.endsWith("/review") && method === "POST") {
      expect(actor).toBe(reviewer);
      const input = route.request().postDataJSON() as { expected_version: number; note: string; review_due_on: string };
      expect(input.expected_version).toBe(1);
      const snapshot: ContextRecord = {
        ...phases[0].snapshot, status: "active", row_version: 2, updated_by_user_id: reviewer,
        reviewed_at: "2026-11-26T12:01:00Z", decision_note: input.note, review_due_on: input.review_due_on,
      };
      phases.unshift({ command: "reviewed", snapshot });
      return ok(snapshot);
    }
    if (path.endsWith("/history")) return ok(phases);
    if (withProcess && path.startsWith(`/context/interested-parties/${recordId}/process-`)) {
      const current = phases[0].snapshot;
      const envelope = { party_id: recordId, tenant_id: tenant, unit_id: firstUnit, party_version: current.row_version };
      expect(unit).toBe(firstUnit);
      expect(actor).toBe(author);
      if (path.endsWith("/process-candidates")) return ok({ ...envelope, items: [process], has_more: false });
      if (method === "GET") return ok({ ...envelope, items: link ? [link] : [], has_more: false });
      expect(route.request().headers()["x-csrf-token"]).toBe(csrf);
      const input = route.request().postDataJSON();
      expect(input.expected_party_version).toBe(current.row_version);
      const version = current.row_version + 1;
      phases.unshift({ command: "updated", snapshot: {
        ...current, status: "draft", row_version: version, updated_by_user_id: actor,
        reviewed_at: null, decision_note: "",
      } });
      if (path.endsWith("/remove") && link) {
        link = { ...link, removed_party_version: version, removed_at: "2026-11-26T12:02:00Z", removal_reason: input.reason };
        return ok({ ...envelope, party_version: version, link_id: linkId, action: "removed" });
      }
      expect(input.process_id).toBe(process.id);
      expect(input.requirement_id).toBe(purchaseRequirement.id);
      expect(input.expected_process_version).toBe(process.row_version);
      link = {
        id: linkId, requirement_id: purchaseRequirement.id, process_id: process.id,
        requirement_snapshot: purchaseRequirement, process_code: process.code, process_name: process.name,
        process_version: process.row_version, linked_party_version: version, rationale: input.rationale,
        created_at: "2026-11-26T12:01:00Z", removed_party_version: null, removed_at: null, removal_reason: "",
        requirement_current: true, process_state: "current",
      };
      return ok({ ...envelope, party_version: version, link_id: linkId, action: "linked" }, 201);
    }
    if (path === "/context/interested-parties") {
      if (foreignPayload) return ok([{ ...phases[0].snapshot, unit_id: firstUnit }]);
      return ok(unit === firstUnit && phases.length ? [phases[0].snapshot] : []);
    }
    return ok({}, 404);
  });
  return { useReviewer: () => { actor = reviewer; }, sendPreviousUnit: () => { foreignPayload = true; } };
}

async function openRegister(page: Page, unitId = firstUnit) {
  if (page.url().endsWith("/#implementation-guide-heading")) await page.reload();
  else await page.goto("/#implementation-guide-heading");
  await page.getByRole("combobox", { name: "Organizational unit", exact: true }).selectOption(unitId);
  const region = page.getByRole("region", { name: "Context and interested parties" });
  await region.getByRole("button", { name: "View context register" }).click();
  await region.getByRole("combobox", { name: "Register", exact: true }).selectOption("interested-parties");
  return region;
}

test("author and independent reviewer use the guided register at mobile width", async ({ page }) => {
  const state = await fixture(page);
  await page.setViewportSize({ width: 375, height: 812 });
  let register = await openRegister(page);
  await expect(register.getByText("No records match this view.")).toBeVisible();
  await register.getByRole("button", { name: "New interested party" }).click();
  await expect(page.getByRole("combobox", { name: "Organizational unit", exact: true })).toBeDisabled();
  await register.getByLabel("Code", { exact: true }).fill("PARTY-01");
  await register.getByLabel("Name", { exact: true }).fill("Synthetic component supplier");
  await register.getByLabel("Party type").selectOption("supplier");
  await register.getByLabel("Relevance to the QMS").selectOption("relevant");
  await register.getByLabel("Review due").fill("2099-05-01");
  await register.getByLabel("Needs and expectations").fill("Traceable lots and timely documentation.");
  await register.getByRole("button", { name: "Add requirement" }).click();
  const requirement = register.getByRole("group", { name: "Requirement 1" });
  await requirement.getByLabel("Requirement", { exact: true }).fill("Match each received lot to its certificate.");
  await requirement.getByLabel("Source", { exact: true }).fill("Purchasing requirement PR-12");
  await requirement.getByLabel("QMS decision").selectOption("addressed_by_qms");
  await expect(requirement.getByLabel("Decision rationale")).toHaveJSProperty("required", true);
  await requirement.getByLabel("Decision rationale").fill("Receiving checks each lot before release.");
  await register.getByRole("button", { name: "Save draft" }).click();
  await expect(register.getByRole("heading", { name: "PARTY-01 · Synthetic component supplier" })).toBeVisible();
  await expect(register.getByText("Responsible person · Synthetic quality user")).toBeVisible();
  await expect(register.getByRole("button", { name: "Review PARTY-01" })).toHaveCount(0);
  await register.getByText("Requirements (1)", { exact: true }).click();
  await expect(register.getByText("Address in the QMS · Purchasing requirement PR-12")).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include(".context-register")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);

  state.useReviewer();
  register = await openRegister(page);
  await expect(register.getByRole("button", { name: "New interested party" })).toHaveCount(0);
  await register.getByRole("button", { name: "Review PARTY-01" }).click();
  await register.getByLabel("Review decision and rationale").fill("Requirements reviewed with purchasing.");
  await register.getByRole("button", { name: "Record review" }).click();
  await expect(register.getByText("PARTY-01 · Reviewed · Version 2")).toBeVisible();
  await register.getByRole("button", { name: "Version history" }).click();
  await expect(register.getByText(/^Version 1 · Created/)).toBeVisible();
  await expect(register.getByText(/^Version 2 · Reviewed/)).toBeVisible();
  const original = register.getByRole("listitem").filter({ hasText: /^Version 1 · Created/ });
  await original.getByText(/^Version 1 · Created/).click();
  await original.getByText("Requirements (1)", { exact: true }).click();
  await expect(original.getByText("Match each received lot to its certificate.")).toBeVisible();

  state.sendPreviousUnit();
  register = await openRegister(page, secondUnit);
  await expect(register.getByRole("alert")).toContainText("Your access or company changed");
  await expect(register.getByRole("heading", { name: "PARTY-01 · Synthetic component supplier" })).toHaveCount(0);
});

test("an authorized author links and withdraws a process while readers without source access see no reference", async ({ page }) => {
  const state = await fixture(page, true);
  await page.setViewportSize({ width: 375, height: 812 });
  let register = await openRegister(page);
  await register.getByRole("button", { name: "View process links" }).click();
  await register.getByRole("button", { name: "Link a process" }).click();
  const links = register.getByRole("region", { name: "Process links", exact: true });
  await links.getByRole("combobox", { name: "Process", exact: true }).selectOption(process.id);
  await links.getByLabel("How this process addresses the requirement").fill("Inspect against the lot certificate.");
  await expect(links.getByText("Changing a process link sends this party back for independent review.")).toBeVisible();
  await links.getByRole("button", { name: "Save process link" }).click();
  await expect(register.getByText("Process linked and party version updated.")).toBeVisible();
  await expect(links.getByText("RECV-01 · Receiving inspection")).toBeVisible();
  await expect(links.getByText("Linked at party version 3")).toBeVisible();
  await expect(register.getByText(/^Pending review · Supplier/)).toBeVisible();
  await links.getByRole("button", { name: "Withdraw RECV-01" }).click();
  await links.getByLabel("Reason for withdrawal").fill("Replaced during the scope review.");
  await links.getByRole("button", { name: "Withdraw link", exact: true }).click();
  await expect(links.getByText(/^Withdrawn at party version 4 · Replaced/)).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include(".party-process-links")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);

  state.useReviewer();
  register = await openRegister(page);
  await expect(register.getByRole("button", { name: "Review PARTY-01" })).toBeVisible();
  await expect(register.getByRole("button", { name: "View process links" })).toHaveCount(0);
  await expect(register.getByText("RECV-01 · Receiving inspection")).toHaveCount(0);
});
