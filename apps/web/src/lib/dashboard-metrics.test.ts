import { describe, expect, it } from "vitest";

import { visibleDashboardMetrics } from "./dashboard-metrics";
import { workspaceSectionsForContext } from "./workspace-navigation";

describe("dashboard metric visibility", () => {
  it("does not reveal quality metrics to an owner without QMS grants", () => {
    expect(visibleDashboardMetrics(workspaceSectionsForContext("owner", []))).toEqual([]);
  });

  it("only shows metrics linked to the collaborator's granted modules", () => {
    const metrics = visibleDashboardMetrics(workspaceSectionsForContext("member", ["documents.read", "risks.manage"]));
    expect(metrics.map((metric) => metric.module)).toEqual(["documents", "risks"]);
  });

  it("never creates fake values and does not duplicate metrics", () => {
    const metrics = visibleDashboardMetrics(workspaceSectionsForContext("member", ["documents.read", "risks.manage", "capa.read", "nonconformities.read"]));
    expect(new Set(metrics.map((metric) => metric.module)).size.toBe(metrics.length);
    expect(metrics.every((metric) => !("value" in metric))).toBe(true);
  });

  it("renders no metric links when no sections are visible", () => {
    expect(visibleDashboardMetrics([])).toEqual([]);
  });
});
