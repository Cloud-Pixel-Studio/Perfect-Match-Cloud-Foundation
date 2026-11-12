import { describe, expect, it } from "vitest";

import { auditLabel, buildAuditDiff, formatAuditValue } from "./audit-view";

describe("audit presentation", () => {
  it("builds a stable field-level comparison from declared and observed values", () => {
    expect(buildAuditDiff(
      ["status", "owner_id"],
      { status: "draft", title: "Calibration", owner_id: null },
      { status: "approved", title: "Calibration", owner_id: "user-1" },
    )).toEqual([
      { field: "owner_id", before: null, after: "user-1", changed: true },
      { field: "status", before: "draft", after: "approved", changed: true },
      { field: "title", before: "Calibration", after: "Calibration", changed: false },
    ]);
  });

  it("formats missing, boolean and structured evidence without HTML", () => {
    expect(formatAuditValue(null)).toBe("Not set");
    expect(formatAuditValue(false)).toBe("No");
    expect(formatAuditValue({ score: 12 })).toBe('{\n  "score": 12\n}');
  });

  it("turns internal identifiers into readable labels", () => {
    expect(auditLabel("qms.access_granted")).toBe("Qms · Access Granted");
  });
});
