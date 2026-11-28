const allowedRoots = new Set([
  "context",
  "auth", "tenant", "audit", "organization", "action-center", "workflows", "workflow-instances", "qms-access", "qms-projects", "processes", "controls", "control-instances", "control-activities", "control-evidence-requirements", "control-instance-activities", "control-instance-evidence", "documents", "risks", "nonconformities", "capas", "internal-audits",
]);
const namedSegment = /^[a-z][a-z-]*$/;
const uuidSegment = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isAllowedIdentityPath(path: string[]): boolean {
  if (path[0] === "employees") {
    return path.length >= 2 && path.length <= 4 && uuidSegment.test(path[1])
      && (path.length < 3 || uuidSegment.test(path[2]))
      && (path.length < 4 || path[3] === "archive" || path[3] === "restore");
  }
  return path.length > 0 && path.length <= 16 && allowedRoots.has(path[0]) &&
    path.slice(1).every((segment) => namedSegment.test(segment) || uuidSegment.test(segment));
}
