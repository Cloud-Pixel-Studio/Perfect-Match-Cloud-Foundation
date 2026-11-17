import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync(new URL("../app/styles.css", import.meta.url), "utf8");
const shell = readFileSync(new URL("../components/identity-shell.tsx", import.meta.url), "utf8");
const access = readFileSync(new URL("../components/qms-access-workspace.tsx", import.meta.url), "utf8");
const products = readFileSync(new URL("../app/products/page.tsx", import.meta.url), "utf8");
const capaTrace = readFileSync(new URL("../components/capa-trace-links.tsx", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../components/workflow-workspace.tsx", import.meta.url), "utf8");
const dialog = readFileSync(new URL("../components/modal-dialog.tsx", import.meta.url), "utf8");
const audit = readFileSync(new URL("../components/audit-workspace.tsx", import.meta.url), "utf8");

describe("interface design contracts", () => {
  it("provides keyboard navigation directly to the active workspace", () => {
    expect(shell).toContain('className="skip-link"');
    expect(shell).toContain('id="qms-active-workspace"');
    expect(styles).toContain(".skip-link:focus");
  });

  it("turns permission history into labelled mobile records", () => {
    for (const label of ["Member", "Responsibility", "Scope", "Status", "Granted", "Action"]) {
      expect(access).toContain(`data-label="${label}"`);
    }
    expect(styles).toContain(".qms-table-scroll .qms-access-table td::before");
    expect(styles).toContain("content: attr(data-label)");
  });

  it("defines visible feedback and interaction states", () => {
    expect(styles).toContain(".workflow-message");
    expect(styles).toContain(".denied-state");
    expect(styles).toContain(".secondary-action:hover:not(:disabled)");
    expect(styles).toContain(".primary-action:active:not(:disabled)");
  });

  it("presents the commercial model without conflating seats and authority", () => {
    expect(products).toContain("Perfect Match QMS");
    expect(products).toContain("Seats inside your company space");
    expect(products).toContain("ISO addons by standard and edition");
    expect(products).toContain("Access and approval responsibilities stay separately assigned");
    expect(products).toContain("Commercial rollout and pricing are still in preparation");
  });

  it("distinguishes direct CAPA traceability and independently accepted evidence", () => {
    expect(capaTrace).toContain("Direct traceability");
    expect(capaTrace).toContain("Evidence must be independently accepted");
    expect(capaTrace).toContain("expected_link_version");
    expect(capaTrace).toContain("Reason for removal");
  });

  it("uses a keyboard accessible dialog for workflow editing", () => {
    expect(workflow).not.toContain("window.prompt");
    expect(workflow).toContain("<ModalDialog");
    expect(dialog).toContain("dialog.showModal()");
    expect(dialog).toContain("onCancel=");
    expect(styles).toContain(".modal-dialog::backdrop");
  });

  it("presents audit evidence with filters and field-level differences", () => {
    expect(audit).toContain("Filter audit history");
    expect(audit).toContain("buildAuditDiff");
    expect(audit).toContain("Load older events");
    expect(styles).toContain(".audit-diff-row.changed");
  });
});
