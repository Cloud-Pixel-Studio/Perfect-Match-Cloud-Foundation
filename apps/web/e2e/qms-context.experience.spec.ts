import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import type { ContextFields, ContextKind, ContextRecord, PartyRequirement, PartySource, PartySourceLink, ScopeBasisCitation, ScopeBasisReference } from "../src/lib/qms-context";

const tenant = "10000000-0000-4000-8000-000000000001";
const author = "20000000-0000-4000-8000-000000000001";
const reviewer = "20000000-0000-4000-8000-000000000002";
const firstUnit = "30000000-0000-4000-8000-000000000001";
const secondUnit = "30000000-0000-4000-8000-000000000002";
const recordId = "40000000-0000-4000-8000-000000000001";
const csrf = "synthetic-test-csrf-token";
const process = { id: "50000000-0000-4000-8000-000000000001", code: "RECV-01", name: "Receiving inspection", row_version: 7 };
const candidateDocument = {
  id: "50000000-0000-4000-8000-000000000002", document_id: "50000000-0000-4000-8000-000000000003",
  code: "SOP-01", name: "Receiving procedure", row_version: 3, document_version: 4, revision: "B",
};
const candidateEvidence = {
  id: "50000000-0000-4000-8000-000000000004", control_instance_id: "50000000-0000-4000-8000-000000000005",
  code: "CTRL-01", name: "Lot check record", row_version: 3, instance_version: 4, evidence_type: "record",
};
const candidateRisk = {
  id: "50000000-0000-4000-8000-000000000006", code: "OPP-01", name: "Earlier certificate confirmation",
  row_version: 2, state: "assessed", risk_type: "opportunity",
} as const;
const candidatesBySource = { process, document: candidateDocument, evidence: candidateEvidence, risk: candidateRisk };
const sourcePermissions = { process: "processes.read", document: "documents.read", evidence: "control_instances.read", risk: "risks.read" };
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
const scopeIssue: ContextRecord = {
  ...seededParty, id: "40000000-0000-4000-8000-000000000002", kind: "issues", code: "CTX-01",
  name: "Receiving disruptions", classification: "external", category: "environmental", party_requirements: [],
};
const basisSources: ScopeBasisCitation[] = [
  { record_id: scopeIssue.id, source_version: 2, kind: "issues", code: scopeIssue.code, name: scopeIssue.name,
    requirement_id: null, requirement_statement: null },
  { record_id: seededParty.id, source_version: 2, kind: "interested-parties", code: seededParty.code,
    name: seededParty.name, requirement_id: purchaseRequirement.id, requirement_statement: purchaseRequirement.statement },
];

async function fixture(page: Page, scenario?: PartySource | "scope") {
  const source = scenario === "scope" ? undefined : scenario;
  let actor = author;
  let scopeRecord: ContextRecord | null = null;
  let approvedScope: ContextRecord | null = null;
  let foreignPayload = false;
  let link: PartySourceLink | null = null;
  let phases: Array<{ command: string; snapshot: ContextRecord }> = source ? [{ command: "reviewed", snapshot: seededParty }] : [];
  const capabilities = () => [
    "context.read", actor === author ? "context.manage" : "context.review",
    ...(source && actor === author ? [sourcePermissions[source]] : []),
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
    if (path === "/processes" || path === "/documents") return ok([]);
    if (path === "/context/issues") return ok(scenario === "scope" && unit === firstUnit && url.searchParams.get("status") === "active" ? [scopeIssue] : []);
    if (path === "/context/interested-parties" && scenario === "scope" && unit === firstUnit
      && url.searchParams.get("status") === "active") return ok([seededParty]);
    if (scenario === "scope" && path.startsWith("/context/qms-scope")) {
      if (path.endsWith("/current")) return ok(approvedScope);
      if (method === "GET") return ok(scopeRecord && unit === firstUnit ? [scopeRecord] : []);
      expect(route.request().headers()["x-csrf-token"]).toBe(csrf);
      const input = route.request().postDataJSON();
      if (path.endsWith("/review")) {
        if (!scopeRecord) throw new Error("No scope draft to approve");
        expect(actor).toBe(reviewer);
        expect(input.expected_version).toBe(scopeRecord.row_version);
        approvedScope = {
          ...scopeRecord, status: "active", row_version: scopeRecord.row_version + 1,
          updated_by_user_id: reviewer, decision_note: input.note, review_due_on: input.review_due_on,
          reviewed_at: "2026-11-27T12:01:00Z",
        };
        scopeRecord = approvedScope;
        return ok(scopeRecord);
      }
      expect(actor).toBe(author);
      expect(input.scope_definition.applicability).toBe("exceptions");
      expect(input.scope_definition.non_applicability).toBe("8.3: The customer supplies the design.");
      if (method === "PATCH") expect(input.expected_version).toBe(scopeRecord?.row_version);
      const references = input.scope_basis as ScopeBasisReference[];
      expect(references).toHaveLength(method === "PATCH" ? 1 : 2);
      const citations = references.map(reference => {
        const source = basisSources.find(item => item.record_id === reference.record_id
          && item.source_version === reference.source_version && item.requirement_id === reference.requirement_id);
        if (!source) throw new Error("No reviewed record for the supplied basis reference");
        return source;
      });
      scopeRecord = {
        ...input, id: recordId, tenant_id: tenant, unit_id: firstUnit, kind: "qms-scope",
        status: "draft", row_version: (scopeRecord?.row_version ?? 0) + 1,
        created_by_user_id: author, content_editor_user_id: author, updated_by_user_id: author,
        updated_at: "2026-11-27T12:00:00Z", reviewed_at: null, decision_note: "", scope_basis: citations,
      };
      return ok(scopeRecord, method === "PATCH" ? 200 : 201);
    }
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
        owner_display_name: "Synthetic quality user", scope_basis: [],
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
    if (source && path.startsWith(`/context/interested-parties/${recordId}/${source}-`)) {
      const current = phases[0].snapshot;
      const envelope = { party_id: recordId, tenant_id: tenant, unit_id: firstUnit, party_version: current.row_version };
      expect(unit).toBe(firstUnit);
      expect(actor).toBe(author);
      if (path.endsWith("-candidates")) return ok({ ...envelope, items: [candidatesBySource[source]], has_more: false });
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
      expect(input.requirement_id).toBe(purchaseRequirement.id);
      const common = {
        id: linkId, requirement_id: purchaseRequirement.id, requirement_snapshot: purchaseRequirement,
        linked_party_version: version, rationale: input.rationale,
        created_at: "2026-11-26T12:01:00Z", removed_party_version: null, removed_at: null, removal_reason: "",
        requirement_current: true,
      };
      if (source === "risk") {
        expect(input.risk_id).toBe(candidateRisk.id);
        expect(input.expected_risk_version).toBe(candidateRisk.row_version);
        link = {
          ...common, risk_id: candidateRisk.id, risk_code: candidateRisk.code, risk_name: candidateRisk.name,
          risk_type: candidateRisk.risk_type, linked_risk_state: candidateRisk.state,
          risk_version: candidateRisk.row_version, risk_state: "closed", risk_changed: true,
        };
      } else if (source === "evidence") {
        expect(input.evidence_id).toBe(candidateEvidence.id);
        expect(input.control_instance_id).toBe(candidateEvidence.control_instance_id);
        expect(input.expected_evidence_version).toBe(candidateEvidence.row_version);
        expect(input.expected_instance_version).toBe(candidateEvidence.instance_version);
        link = {
          ...common, evidence_id: candidateEvidence.id, control_instance_id: candidateEvidence.control_instance_id,
          control_code: candidateEvidence.code, evidence_name: candidateEvidence.name,
          evidence_type: candidateEvidence.evidence_type, accepted_at: "2026-11-25T10:00:00Z",
          evidence_version: candidateEvidence.row_version, instance_version: candidateEvidence.instance_version,
          evidence_state: "current",
        };
      } else if (source === "document") {
        expect(input.document_id).toBe(candidateDocument.document_id);
        expect(input.document_revision_id).toBe(candidateDocument.id);
        expect(input.expected_document_version).toBe(candidateDocument.document_version);
        expect(input.expected_revision_version).toBe(candidateDocument.row_version);
        link = {
          ...common, document_id: candidateDocument.document_id, document_revision_id: candidateDocument.id,
          document_code: candidateDocument.code, document_title: candidateDocument.name, revision: candidateDocument.revision,
          file_sha256: "a".repeat(64), document_version: candidateDocument.document_version,
          revision_version: candidateDocument.row_version, document_state: "current",
        };
      } else {
        expect(input.process_id).toBe(process.id);
        expect(input.expected_process_version).toBe(process.row_version);
        link = {
          ...common, process_id: process.id, process_code: process.code, process_name: process.name,
          process_version: process.row_version, process_state: "current",
        };
      }
      return ok({ ...envelope, party_version: version, link_id: linkId, action: "linked" }, 201);
    }
    if (path === "/context/interested-parties") {
      if (foreignPayload) return ok([{ ...phases[0].snapshot, unit_id: firstUnit }]);
      return ok(unit === firstUnit && phases.length ? [phases[0].snapshot] : []);
    }
    return ok({}, 404);
  });
  return {
    useReviewer: () => { actor = reviewer; },
    useAuthor: () => { actor = author; },
    sendPreviousUnit: () => { foreignPayload = true; },
  };
}

async function openRegister(page: Page, unitId = firstUnit, kind: ContextKind = "interested-parties") {
  if (page.url().endsWith("/#implementation-guide-heading")) await page.reload();
  else await page.goto("/#implementation-guide-heading");
  await page.getByRole("combobox", { name: "Organizational unit", exact: true }).selectOption(unitId);
  const region = page.getByRole("region", { name: "Context and interested parties" });
  await region.getByRole("button", { name: "View context register" }).click();
  await region.getByRole("combobox", { name: "Register", exact: true }).selectOption(kind);
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
  const state = await fixture(page, "process");
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

test("an author cites the exact released document revision and source permission protects its history", async ({ page }) => {
  const state = await fixture(page, "document");
  await page.setViewportSize({ width: 375, height: 812 });
  let register = await openRegister(page);
  await expect(register.getByRole("button", { name: "View process links" })).toHaveCount(0);
  await register.getByRole("button", { name: "View document links" }).click();
  const links = register.getByRole("region", { name: "Document links", exact: true });
  await links.getByRole("button", { name: "Link a document" }).click();
  await links.getByRole("combobox", { name: "Document", exact: true }).selectOption(candidateDocument.id);
  await links.getByLabel("How this document addresses the requirement").fill("Specifies certificate checks before release.");
  await links.getByRole("button", { name: "Save document link" }).click();
  await expect(register.getByText("Document linked and party version updated.")).toBeVisible();
  await expect(links.getByText("Current released revision · Linked revision B")).toBeVisible();
  await links.getByText("Document fingerprint", { exact: true }).click();
  await expect(links.getByText("a".repeat(64), { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  await links.getByRole("button", { name: "Withdraw SOP-01" }).click();
  await links.getByLabel("Reason for withdrawal").fill("Replaced by a different released procedure.");
  await links.getByRole("button", { name: "Withdraw link", exact: true }).click();
  await expect(links.getByText(/^Withdrawn at party version 4/)).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include(".party-document-links")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  state.useReviewer();
  register = await openRegister(page);
  await expect(register.getByRole("button", { name: "Review PARTY-01" })).toBeVisible();
  await expect(register.getByRole("button", { name: "View document links" })).toHaveCount(0);
});

test("accepted evidence keeps a dated historical citation and requires evidence source access", async ({ page }) => {
  const state = await fixture(page, "evidence");
  await page.setViewportSize({ width: 375, height: 812 });
  let register = await openRegister(page);
  await expect(register.getByRole("button", { name: "View document links" })).toHaveCount(0);
  await register.getByRole("button", { name: "View evidence links" }).click();
  const links = register.getByRole("region", { name: "Evidence links", exact: true });
  await links.getByRole("button", { name: "Link evidence", exact: true }).click();
  await links.getByRole("combobox", { name: "Evidence", exact: true }).selectOption(candidateEvidence.id);
  await links.getByLabel("How this evidence addresses the requirement").fill("Shows the lot was examined before release.");
  await links.getByRole("button", { name: "Save evidence link" }).click();
  await expect(register.getByText("Evidence linked and party version updated.")).toBeVisible();
  await expect(links.getByText("Accepted evidence · Linked evidence version 3")).toBeVisible();
  await expect(links.locator("time")).toHaveAttribute("datetime", "2026-11-25T10:00:00Z");
  await links.getByRole("button", { name: "Withdraw CTRL-01" }).click();
  await links.getByLabel("Reason for withdrawal").fill("The receiving example is replaced.");
  await links.getByRole("button", { name: "Withdraw link", exact: true }).click();
  await expect(links.getByText("Withdrawn at party version 4 · The receiving example is replaced.")).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include(".party-evidence-links")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  state.useReviewer();
  register = await openRegister(page);
  await expect(register.getByRole("button", { name: "Review PARTY-01" })).toBeVisible();
  await expect(register.getByRole("button", { name: "View evidence links" })).toHaveCount(0);
});

test("the current opportunity state and the cited state are both visible to authorized users", async ({ page }) => {
  const state = await fixture(page, "risk");
  await page.setViewportSize({ width: 375, height: 812 });
  let register = await openRegister(page);
  await register.getByRole("button", { name: "View risk links" }).click();
  const links = register.getByRole("region", { name: "Risk links", exact: true });
  await links.getByRole("button", { name: "Link a risk or opportunity", exact: true }).click();
  const source = links.getByRole("combobox", { name: "Risk or opportunity", exact: true });
  await expect(source.getByRole("option", { name: /Opportunity · Assessed/ })).toHaveCount(1);
  await source.selectOption(candidateRisk.id);
  await links.getByLabel("How this risk or opportunity relates to the requirement").fill("Confirms the certificate before the lot arrives.");
  await links.getByRole("button", { name: "Save risk link" }).click();
  await expect(register.getByText("Risk or opportunity linked and party version updated.")).toBeVisible();
  await expect(links.getByText("Closed · Linked risk register version 2")).toBeVisible();
  await expect(links.getByText("Opportunity · State when linked: Assessed · Register has changed")).toBeVisible();
  await links.getByRole("button", { name: "Withdraw OPP-01" }).click();
  await links.getByLabel("Reason for withdrawal").fill("Review completed for this opportunity.");
  await links.getByRole("button", { name: "Withdraw link", exact: true }).click();
  await expect(links.getByText("Withdrawn at party version 4 · Review completed for this opportunity.")).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include(".party-risk-links")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
  state.useReviewer();
  register = await openRegister(page);
  await expect(register.getByRole("button", { name: "Review PARTY-01" })).toBeVisible();
  await expect(register.getByRole("button", { name: "View risk links" })).toHaveCount(0);
});

test("the QMS scope retains its approval while an author edits the next version", async ({ page }) => {
  const state = await fixture(page, "scope");
  await page.setViewportSize({ width: 375, height: 812 });
  let register = await openRegister(page, firstUnit, "qms-scope");
  await register.getByRole("button", { name: "Define QMS scope", exact: true }).click();
  await register.getByLabel("Scope title").fill("Assembly QMS");
  await register.getByLabel("QMS boundaries").fill("Receiving through dispatch.");
  await register.getByLabel("Products and services covered").fill("Assembly and inspection of demonstration components.");
  await register.getByLabel("Context and interested-party requirements considered").fill("Receiving disruption CTX-01 and requirement REQ-04.");
  const basis = register.getByRole("region", { name: "Scope basis references" });
  await basis.getByRole("button", { name: "Choose reviewed sources" }).click();
  const reviewed = basis.getByRole("combobox", { name: "Reviewed source" });
  await reviewed.selectOption({ label: "CTX-01 · Receiving disruptions · Version 2" });
  await basis.getByRole("button", { name: "Add reference" }).click();
  await basis.getByRole("combobox", { name: "Source type" }).selectOption("interested-parties");
  await reviewed.selectOption({ label: "PARTY-01 · Match each received lot to its certificate. · Version 2" });
  await basis.getByRole("button", { name: "Add reference" }).click();
  await register.getByLabel("Review due").fill("2099-05-01");
  await register.getByLabel("Applicability of requirements").selectOption("exceptions");
  await register.getByLabel("Requirements that do not apply and their justification").fill("8.3: The customer supplies the design.");
  await register.getByRole("button", { name: "Save draft" }).click();
  await expect(register.getByText("Scope draft saved · Version 1")).toBeVisible();
  await expect(register.getByText("There is no approved scope yet.")).toBeVisible();
  await expect(register.getByRole("button", { name: "Review scope for approval" })).toHaveCount(0);
  state.useReviewer();
  register = await openRegister(page, firstUnit, "qms-scope");
  await register.getByRole("button", { name: "Review scope for approval" }).click();
  await register.getByLabel("Review decision and rationale").fill("The documented boundaries match operations.");
  await register.getByRole("button", { name: "Approve scope" }).click();
  await expect(register.getByText("Approved scope · Version 2")).toBeVisible();

  state.useAuthor();
  register = await openRegister(page, firstUnit, "qms-scope");
  await register.getByRole("button", { name: "Edit scope" }).click();
  await register.getByLabel("QMS boundaries").fill("Receiving through dispatch and packaging.");
  await register.getByRole("button", { name: "Remove Receiving disruptions from scope basis" }).click();
  await register.getByRole("button", { name: "Save draft" }).click();
  const approved = register.getByRole("region", { name: "Current approved scope" });
  await expect(approved.getByText(/Approved · Version 2/)).toBeVisible();
  await expect(approved.getByText(/Receiving through dispatch\./)).toBeVisible();
  await expect(approved.getByText("CTX-01 · Receiving disruptions")).toBeVisible();
  await expect(approved.getByText("Match each received lot to its certificate.")).toBeVisible();
  await expect(register.getByText(/Pending approval · Version 3/)).toBeVisible();
  await expect(register.getByText("CTX-01 · Receiving disruptions", { exact: true })).toHaveCount(1);
  await expect(register.getByText(/Receiving through dispatch and packaging\./)).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include(".context-register")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(accessibility.violations).toEqual([]);
});
