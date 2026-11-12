export type WorkspaceId =
  | "overview"
  | "actions"
  | "processes"
  | "documents"
  | "controls"
  | "internal-audits"
  | "risks"
  | "nonconformities"
  | "capa"
  | "organization"
  | "permissions"
  | "workflows"
  | "audit";

export type WorkspaceItem = {
  id: WorkspaceId;
  label: string;
  description: string;
  hash: string;
};

export type WorkspaceTargetSource = "workflow" | "capa" | "control_activity" | "evidence_review";

export type WorkspaceTarget = {
  recordId: string;
  subrecordId?: string;
  source: WorkspaceTargetSource;
  unitId?: string;
  processId?: string;
};

const targetKeys = ["pm_record", "pm_subrecord", "pm_source", "pm_unit", "pm_process"] as const;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const targetSources = new Set<WorkspaceTargetSource>(["workflow", "capa", "control_activity", "evidence_review"]);

export const workspaceSections: { label: string; items: WorkspaceItem[] }[] = [
  {
    label: "My work",
    items: [
      { id: "overview", label: "Overview", description: "Choose the work you need to do.", hash: "overview-heading" },
      { id: "actions", label: "Action center", description: "Prioritize assigned work and pending reviews.", hash: "action-center-heading" },
    ],
  },
  {
    label: "Coordination",
    items: [
      { id: "workflows", label: "Workflows", description: "Complete controlled approvals and assigned tasks.", hash: "workflow-heading" },
    ],
  },
  {
    label: "Quality operations",
    items: [
      { id: "processes", label: "Processes", description: "Map and manage your processes.", hash: "process-title" },
      { id: "documents", label: "Documents", description: "Control revisions and release.", hash: "documents-heading" },
      { id: "controls", label: "Controls & evidence", description: "Implement controls and review evidence.", hash: "controls-heading" },
      { id: "internal-audits", label: "Internal audits", description: "Plan audit programs, schedules and responsibilities.", hash: "internal-audits-heading" },
    ],
  },
  {
    label: "Improvement",
    items: [
      { id: "risks", label: "Risks & opportunities", description: "Assess exposure and follow up.", hash: "risks-heading" },
      { id: "nonconformities", label: "Nonconformities", description: "Contain and resolve issues.", hash: "ncr-heading" },
      { id: "capa", label: "Corrective actions", description: "Register cases and investigate root causes.", hash: "capa-heading" },
    ],
  },
  {
    label: "Administration",
    items: [
      { id: "organization", label: "Organization", description: "Units, assignments and scope.", hash: "organization-workspace-heading" },
      { id: "permissions", label: "Permissions", description: "Grant explicit QMS responsibilities.", hash: "qms-access-heading" },
      { id: "audit", label: "Audit trail", description: "Review recorded changes.", hash: "audit-heading" },
    ],
  },
];

export const workspaceItems = workspaceSections.flatMap((section) => section.items);

const capabilityFamilies: Partial<Record<WorkspaceId, string[]>> = {
  processes: ["processes."],
  documents: ["documents."],
  controls: ["controls.", "control_instances."],
  "internal-audits": ["audits."],
  risks: ["risks."],
  nonconformities: ["ncr."],
  capa: ["capa."],
};

export function workspaceSectionsForContext(role: string, capabilities: Iterable<string>) {
  const assigned = [...capabilities];
  const administration = role === "owner" || role === "admin";
  const assurance = administration || role === "auditor";
  const visible = (id: WorkspaceId) => {
    if (id === "overview" || id === "actions" || id === "workflows" || id === "permissions") return true;
    if (id === "organization" || id === "audit") return assurance;
    return (capabilityFamilies[id] ?? []).some((prefix) => assigned.some((capability) => capability.startsWith(prefix)));
  };
  return workspaceSections
    .map((section) => ({ ...section, items: section.items.filter((item) => visible(item.id)) }))
    .filter((section) => section.items.length > 0);
}

export function workspaceFromHash(hash: string): WorkspaceId {
  const fragment = hash.replace(/^#/, "");
  return workspaceItems.find((item) => item.hash === fragment)?.id ?? "overview";
}

export function workspaceTargetFromSearch(search: string): WorkspaceTarget | null {
  const params = new URLSearchParams(search);
  const recordId = params.get("pm_record") ?? "";
  const source = params.get("pm_source") as WorkspaceTargetSource | null;
  if (!uuidPattern.test(recordId) || !source || !targetSources.has(source)) return null;
  const optionalUuid = (key: "pm_subrecord" | "pm_unit" | "pm_process") => {
    const value = params.get(key) ?? "";
    return uuidPattern.test(value) ? value : undefined;
  };
  return {
    recordId,
    source,
    subrecordId: optionalUuid("pm_subrecord"),
    unitId: optionalUuid("pm_unit"),
    processId: optionalUuid("pm_process"),
  };
}

export function setWorkspaceTarget(url: URL, target: WorkspaceTarget | null): URL {
  for (const key of targetKeys) url.searchParams.delete(key);
  if (!target) return url;
  url.searchParams.set("pm_record", target.recordId);
  url.searchParams.set("pm_source", target.source);
  if (target.subrecordId) url.searchParams.set("pm_subrecord", target.subrecordId);
  if (target.unitId) url.searchParams.set("pm_unit", target.unitId);
  if (target.processId) url.searchParams.set("pm_process", target.processId);
  return url;
}
