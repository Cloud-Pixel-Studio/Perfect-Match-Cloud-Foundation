import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync(new URL("../app/styles.css", import.meta.url), "utf8");
const shell = readFileSync(new URL("../components/identity-shell.tsx", import.meta.url), "utf8");
const access = readFileSync(new URL("../components/qms-access-workspace.tsx", import.meta.url), "utf8");
const products = readFileSync(new URL("../app/products/page.tsx", import.meta.url), "utf8");
const capaTrace = readFileSync(new URL("../components/capa-trace-links.tsx", import.meta.url), "utf8");

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
    expect(products).toContain("Seats inside each tenant");
    expect(products).toContain("ISO standards by controlled edition");
    expect(products).toContain("A purchased seat or platform role never grants approval authority by itself");
    expect(products).toContain("Availability and pricing are intentionally not shown");
  });

  it("distinguishes direct CAPA traceability and independently accepted evidence", () => {
    expect(capaTrace).toContain("Direct traceability");
    expect(capaTrace).toContain("Evidence must be independently accepted");
    expect(capaTrace).toContain("expected_link_version");
    expect(capaTrace).toContain("Reason for removal");
  });
});
