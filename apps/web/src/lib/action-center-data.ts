export type ActionItem = {
  id: string;
  source: "workflow" | "capa" | "control_activity" | "evidence_review";
  source_id: string;
  unit_id: string | null;
  title: string;
  context: string;
  state: string;
  urgency: "overdue" | "due_soon" | "normal" | "waiting_review";
  due_date: string | null;
  overdue: boolean;
  assigned_to_user_id: string | null;
  assignee_name: string | null;
  target_workspace: "workflows" | "capa" | "controls";
  target_record_id: string;
  target_subrecord_id: string | null;
  target_process_id: string | null;
  updated_at: string;
};

export type ActionCenterResponse = {
  scope: "mine" | "team";
  generated_at: string;
  summary: { total: number; overdue: number; due_soon: number; unassigned: number; by_source: Record<string, number> };
  items: ActionItem[];
};

export type ActionFailure = "expired" | "denied" | "unavailable";

type ActionResult = { ok: true; data: ActionCenterResponse } | { ok: false; reason: ActionFailure };
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0;
const text = (value: unknown) => typeof value === "string" && value.length > 0;
const nullableText = (value: unknown) => value === null || typeof value === "string";
const instant = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));
const date = (value: unknown) => value === null || typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && instant(value) && new Date(value).toISOString().slice(0, 10) === value;

function validQueue(value: unknown, scope: "mine" | "team"): value is ActionCenterResponse {
  if (!object(value) || value.scope !== scope || !instant(value.generated_at) || !object(value.summary) || !Array.isArray(value.items)) return false;
  const summary = value.summary;
  if (![summary.total, summary.overdue, summary.due_soon, summary.unassigned].every(count) || !object(summary.by_source) || !Object.values(summary.by_source).every(count)) return false;
  return value.items.every(item => object(item)
    && [item.id, item.source_id, item.title, item.state, item.target_record_id].every(text)
    && typeof item.context === "string" && typeof item.overdue === "boolean"
    && [item.unit_id, item.assigned_to_user_id, item.assignee_name, item.target_subrecord_id, item.target_process_id].every(nullableText)
    && typeof item.source === "string" && ["workflow", "capa", "control_activity", "evidence_review"].includes(item.source)
    && typeof item.target_workspace === "string" && ["workflows", "capa", "controls"].includes(item.target_workspace)
    && typeof item.urgency === "string" && ["overdue", "due_soon", "normal", "waiting_review"].includes(item.urgency)
    && date(item.due_date) && instant(item.updated_at));
}

/** Fail closed on stale-scope/malformed data; never display upstream diagnostics. */
export async function fetchActions(scope: "mine" | "team", limit: 5 | 100, request: typeof fetch = fetch): Promise<ActionResult> {
  try {
    const response = await request(`/api/identity/action-center?scope=${scope}&limit=${limit}`, { credentials: "include", cache: "no-store" });
    if (!response.ok) return { ok: false, reason: response.status === 401 ? "expired" : response.status === 403 ? "denied" : "unavailable" };
    const data: unknown = await response.json();
    return validQueue(data, scope) ? { ok: true, data } : { ok: false, reason: "unavailable" };
  } catch {
    return { ok: false, reason: "unavailable" };
  }
}
