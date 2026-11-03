const allowedRoots = new Set([
  "auth", "tenant", "audit", "organization", "action-center", "workflows", "workflow-instances", "qms-access", "processes", "controls", "control-instances", "control-activities", "control-evidence-requirements", "control-instance-activities", "control-instance-evidence", "documents", "risks", "nonconformities", "capas",
]);
const namedSegment = /^[a-z][a-z-]*$/;
const uuidSegment = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isAllowedIdentityPath(path: string[]): boolean {
  return path.length > 0 && path.length <= 16 && allowedRoots.has(path[0]) &&
    path.slice(1).every((segment) => namedSegment.test(segment) || uuidSegment.test(segment));
}
