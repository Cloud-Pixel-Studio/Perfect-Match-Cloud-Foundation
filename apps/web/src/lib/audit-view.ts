export type AuditValues = Record<string, unknown> | null;

export type AuditDiffRow = {
  field: string;
  before: unknown;
  after: unknown;
  changed: boolean;
};

export function buildAuditDiff(
  changedFields: string[],
  oldValues: AuditValues,
  newValues: AuditValues,
): AuditDiffRow[] {
  const fields = new Set([
    ...changedFields,
    ...Object.keys(oldValues ?? {}),
    ...Object.keys(newValues ?? {}),
  ]);
  return [...fields].sort().map((field) => {
    const before = oldValues?.[field];
    const after = newValues?.[field];
    return {
      field,
      before,
      after,
      changed: changedFields.includes(field) || JSON.stringify(before) !== JSON.stringify(after),
    };
  });
}

export function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

export function auditLabel(value: string): string {
  return value.replaceAll("_", " ").replaceAll(".", " · ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
