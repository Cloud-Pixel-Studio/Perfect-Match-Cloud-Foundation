import type { WorkspaceId, WorkspaceItem } from "./workspace-navigation";

export type DashboardMetric = {
  label: string;
  detail: string;
  module: WorkspaceId;
};

/** This is a catalog of proposed metrics, NOT live KPI data. */
export const plannedDashboardMetrics: readonly DashboardMetric[] = [
  { label: "Document currency", detail: "Current released revisions", module: "documents" },
  { label: "Overdue corrective actions", detail: "Open CAPA past due date", module: "capa" },
  { label: "High-priority risks", detail: "Active high or critical residual risks", module: "risks" },
  { label: "Nonconformity trend", detail: "Opened and closed records over time", module: "nonconformities" },
];

/** Only expose metric navigation for modules already visible to the user. */
export function visibleDashboardMetrics(
  sections: readonly { items: readonly WorkspaceItem[] }[],
): DashboardMetric[] {
  const visible = new Set(sections.flatMap((section) => section.items.map((item) => item.id)));
  return plannedDashboardMetrics.filter((metric) => visible.has(metric.module));
}

/** Trend preview is relevant only where the viewer can access NCR or CAPA. */
export function canPreviewQualityTrends(metrics: readonly DashboardMetric[]): boolean {
  return metrics.some((metric) => metric.module === "nonconformities" || metric.module === "capa");
}
