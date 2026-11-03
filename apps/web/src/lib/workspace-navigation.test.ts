import { describe, expect, it } from "vitest";

import { setWorkspaceTarget, workspaceFromHash, workspaceItems, workspaceTargetFromSearch } from "./workspace-navigation";

describe("workspace navigation", () => {
  it("preserves every module deep link, including existing NCR and CAPA links", () => {
    for (const item of workspaceItems) {
      expect(workspaceFromHash(`#${item.hash}`)).toBe(item.id);
    }
    expect(workspaceFromHash("#ncr-heading")).toBe("nonconformities");
    expect(workspaceFromHash("#capa-heading")).toBe("capa");
    expect(new Set(workspaceItems.map((item) => item.hash)).size).toBe(workspaceItems.length);
  });

  it("opens overview for unknown or empty fragments", () => {
    expect(workspaceFromHash("")).toBe("overview");
    expect(workspaceFromHash("#unknown-module")).toBe("overview");
  });

  it("round-trips an exact action target without preserving stale target fields", () => {
    const target = {
      recordId: "10000000-0000-4000-8000-000000000001",
      subrecordId: "20000000-0000-4000-8000-000000000001",
      source: "capa" as const,
      unitId: "30000000-0000-4000-8000-000000000001",
      processId: "40000000-0000-4000-8000-000000000001",
    };
    const url = setWorkspaceTarget(new URL("https://qms.example/?keep=yes&pm_record=stale#capa-heading"), target);
    expect(workspaceTargetFromSearch(url.search)).toEqual(target);
    expect(url.searchParams.get("keep")).toBe("yes");
    expect(workspaceTargetFromSearch(setWorkspaceTarget(url, null).search)).toBeNull();
  });

  it("rejects malformed or unsupported action targets", () => {
    expect(workspaceTargetFromSearch("?pm_record=not-a-uuid&pm_source=capa")).toBeNull();
    expect(workspaceTargetFromSearch("?pm_record=10000000-0000-4000-8000-000000000001&pm_source=unknown")).toBeNull();
  });
});
