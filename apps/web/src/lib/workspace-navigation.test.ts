import { describe, expect, it } from "vitest";

import { workspaceFromHash, workspaceItems } from "./workspace-navigation";

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
});
