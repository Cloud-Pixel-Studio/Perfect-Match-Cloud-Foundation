export type WorkspaceId =
  | "overview"
  | "actions"
  | "processes"
  | "documents"
  | "controls"
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

export const workspaceSections: { label: string; items: WorkspaceItem[] }[] = [
  {
    label: "Workspace",
    items: [
      { id: "overview", label: "Overview", description: "Choose the work you need to do.", hash: "overview-heading" },
      { id: "actions", label: "Action center", description: "Prioritize assigned work and pending reviews.", hash: "action-center-heading" },
    ],
  },
  {
    label: "Quality operations",
    items: [
      { id: "processes", label: "Processes", description: "Map and manage your processes.", hash: "process-title" },
      { id: "documents", label: "Documents", description: "Control revisions and release.", hash: "documents-heading" },
      { id: "controls", label: "Controls & evidence", description: "Implement controls and review evidence.", hash: "controls-heading" },
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
      { id: "workflows", label: "Workflows", description: "Manage controlled approvals.", hash: "workflow-heading" },
      { id: "audit", label: "Audit trail", description: "Review recorded changes.", hash: "audit-heading" },
    ],
  },
];

export const workspaceItems = workspaceSections.flatMap((section) => section.items);

export function workspaceFromHash(hash: string): WorkspaceId {
  const fragment = hash.replace(/^#/, "");
  return workspaceItems.find((item) => item.hash === fragment)?.id ?? "overview";
}
