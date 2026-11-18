import { describe, expect, it } from "vitest";

import { journeys, observeGuideStep } from "./guided-journeys";
import type { GuideSnapshot } from "./guided-journey-data";

describe("customer journey guidance", () => {
  it("covers the six customer cases with distinct ordered actionable steps", () => {
    expect(journeys.map(journey => journey.id)).toEqual(["initial", "improve", "transition", "migrate", "audit", "expand"]);
    for (const journey of journeys) {
      expect(journey.steps.length).toBeGreaterThanOrEqual(6);
      expect(new Set(journey.steps.map(step => step.id)).size).toBe(journey.steps.length);
      for (const step of journey.steps) {
        expect([step.title, step.why, step.expected, step.doneWhen].every(value => value.trim().length > 10)).toBe(true);
        expect(step.instructions.length).toBeGreaterThanOrEqual(2);
        expect(Boolean(step.resource || step.productGap)).toBe(true);
      }
    }
  });

  it("keeps normative transition, commercial importing and audit execution explicitly pending", () => {
    const transition = journeys.find(journey => journey.id === "transition")!;
    const migration = journeys.find(journey => journey.id === "migrate")!;
    const audit = journeys.find(journey => journey.id === "audit")!;
    expect(transition.steps.find(step => step.id === "edition-comparison")?.productGap).toContain("not implemented");
    expect(migration.steps.find(step => step.id === "trial-import")?.productGap).toContain("not implemented");
    expect(audit.steps.find(step => step.id === "execute-audit")?.productGap).toContain("not implemented");
  });

  it("requires a selected scope rather than inventing empty results", () => {
    const step = journeys[0].steps.find(step => step.resource === "processes")!;
    expect(observeGuideStep(step, null).kind).toBe("choose_unit");
  });

  it("never interprets existing demo or unrelated records as a completed project step", () => {
    const step = journeys[0].steps.find(step => step.resource === "implementations")!;
    const snapshot = { resources: { implementations: { kind: "loaded", limited: true, records: [{ id: "example", code: "DEMO", name: "Existing control", state: "implemented", qualified: true }] } } } as unknown as GuideSnapshot;
    const observation = observeGuideStep(step, snapshot);
    expect(observation.kind).toBe("loaded");
    expect(observation.qualified).toBe(1);
    expect(observation.limited).toBe(true);
    expect(observation.message).toContain("not verify completion");
    expect(observation).not.toHaveProperty("completed");
    expect(observation).not.toHaveProperty("percent");
  });

  it("separates inaccessible records from an observed empty result", () => {
    const step = journeys[0].steps.find(step => step.resource === "documents")!;
    const snapshot = { resources: { documents: { kind: "restricted" } } } as unknown as GuideSnapshot;
    expect(observeGuideStep(step, snapshot).kind).toBe("restricted");
    snapshot.resources.documents = { kind: "loaded", records: [], limited: false };
    expect(observeGuideStep(step, snapshot)).toMatchObject({ kind: "loaded", records: [], qualified: 0 });
  });

  it("does not give a pending product feature a completion shortcut", () => {
    const step = journeys.find(journey => journey.id === "migrate")!.steps.find(step => step.id === "trial-import")!;
    expect(observeGuideStep(step, null)).toMatchObject({ kind: "feature_pending", records: [], qualified: 0 });
    expect(step.workspace).toBeUndefined();
  });
});
