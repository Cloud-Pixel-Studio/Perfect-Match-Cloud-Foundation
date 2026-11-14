export type QMSGrant = {
  id: string;
  user_id: string;
  unit_id: string;
  capability: string;
  status: "active" | "revoked";
  granted_by_user_id: string;
  created_at: string;
  revoked_by_user_id: string | null;
  revoked_at: string | null;
};

export type QMSHistoryGrant = QMSGrant & {
  member_name: string | null;
  unit_name: string | null;
  unit_code: string | null;
  unit_status: "active" | "archived" | null;
};

export type QMSGrantPage = {
  tenant_id: string;
  viewer_user_id: string;
  viewer_role: string;
  items: QMSHistoryGrant[];
  next_cursor: string | null;
};

export type QMSHistoryFilters = {
  q: string;
  status: "all" | "active" | "revoked";
  capability: string;
  user_id: string;
  unit_id: string;
};

export type QMSHistoryViewer = { userId: string; role: string; tenantId?: string };

export const emptyHistoryFilters: QMSHistoryFilters = {
  q: "", status: "all", capability: "", user_id: "", unit_id: "",
};

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const id = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
const date = (value: unknown): value is string =>
  typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
  Number.isFinite(Date.parse(value));
const optionalText = (value: unknown) => value === null || typeof value === "string";

export function isQMSGrant(value: unknown): value is QMSGrant {
  if (!record(value) || !id(value.id) || !id(value.user_id) || !id(value.unit_id) ||
    !id(value.granted_by_user_id) || typeof value.capability !== "string" ||
    value.capability.length === 0 || !date(value.created_at)) return false;
  return value.status === "active"
    ? value.revoked_at === null && value.revoked_by_user_id === null
    : value.status === "revoked" && date(value.revoked_at) && id(value.revoked_by_user_id);
}

export function historyContextMatches(value: unknown, viewer: QMSHistoryViewer): boolean {
  return record(value) && id(value.tenant_id) && value.viewer_user_id === viewer.userId &&
    value.viewer_role === viewer.role && (!viewer.tenantId || value.tenant_id === viewer.tenantId);
}

export function parseQMSGrantPage(
  value: unknown, viewer: QMSHistoryViewer, limit = 20,
): QMSGrantPage | null {
  if (!historyContextMatches(value, viewer) || !record(value) || !Array.isArray(value.items) ||
    value.items.length > limit || !(value.next_cursor === null ||
      typeof value.next_cursor === "string" && value.next_cursor.length > 0 && value.next_cursor.length <= 2048) ||
    value.next_cursor !== null && value.items.length !== limit) return null;
  if (!value.items.every((item: unknown) => {
    if (!record(item)) return false;
    const details = item;
    return isQMSGrant(item) && optionalText(details.member_name) &&
      optionalText(details.unit_name) && optionalText(details.unit_code) &&
      [null, "active", "archived"].includes(details.unit_status as string | null) &&
      (viewer.role === "owner" || item.user_id === viewer.userId);
  })) return null;
  if (new Set(value.items.map((item: QMSHistoryGrant) => item.id)).size !== value.items.length) return null;
  return value as QMSGrantPage;
}

export function qmsHistoryQuery(filters: QMSHistoryFilters, cursor: string | null, limit = 20): string {
  const query = new URLSearchParams({ limit: String(limit), status: filters.status });
  for (const [key, value] of Object.entries(filters)) {
    if (key !== "status" && value.trim()) query.set(key, value.trim());
  }
  if (cursor) query.set("cursor", cursor);
  return `/qms-access/grants/page?${query.toString()}`;
}

export function grantMatchesFilters(grant: QMSGrant, filters: QMSHistoryFilters): boolean {
  return (!filters.user_id || grant.user_id === filters.user_id) &&
    (!filters.unit_id || grant.unit_id === filters.unit_id) &&
    (!filters.capability || grant.capability === filters.capability) &&
    (filters.status === "all" || grant.status === filters.status);
}

export function matchesGrantCommand(
  value: unknown, viewerId: string,
  target: { user_id: string; unit_id: string; capability: string } | QMSGrant,
  action: "grant" | "revoke",
): value is QMSGrant {
  if (!isQMSGrant(value) || value.user_id !== target.user_id || value.unit_id !== target.unit_id ||
    value.capability !== target.capability) return false;
  if (action === "grant") return value.status === "active" && value.granted_by_user_id === viewerId;
  if (!("id" in target)) return false;
  return value.id === target.id && value.status === "revoked" &&
    value.revoked_by_user_id === viewerId && value.granted_by_user_id === target.granted_by_user_id &&
    value.created_at === target.created_at;
}
