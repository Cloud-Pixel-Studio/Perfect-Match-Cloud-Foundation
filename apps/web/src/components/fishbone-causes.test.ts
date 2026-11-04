import { describe, expect, it } from "vitest";

import { normalizeFishboneData } from "./fishbone-causes";

describe("Fishbone analysis", () => {
  it("keeps a saved single-text cause as an unconfirmed editable cause", () => {
    const normalized = normalizeFishboneData({ people: "Unclear handoff", process: "" });
    expect(normalized.people).toEqual([{
      statement: "Unclear handoff", evidence: "", rationale: "", confirmed: false,
    }]);
    expect(normalized.process).toEqual([]);
  });

  it("keeps multiple confirmed causes and all six fixed categories", () => {
    const saved = [
      { statement: "A", evidence: "Record 1", rationale: "Confirmed", confirmed: true },
      { statement: "B", evidence: "", rationale: "", confirmed: false },
    ];
    const normalized = normalizeFishboneData({ equipment: saved });
    expect(normalized.equipment).toEqual(saved);
    expect(Object.keys(normalized)).toHaveLength(6);
  });
});
