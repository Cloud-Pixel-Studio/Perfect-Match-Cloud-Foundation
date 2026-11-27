export type ContextScope = { tenantId: string; userId: string; unitId: string };
export type ContextKind = "issues" | "interested-parties";
export type ContextState = "draft" | "active" | "retired";
export type ContextRelevance = "relevant" | "not_relevant" | "under_review";
export const requirementDispositions = ["pending", "addressed_by_qms", "outside_qms"] as const;
export type PartyRequirement = {
  id: string;
  statement: string;
  source: string;
  disposition: typeof requirementDispositions[number];
  rationale: string;
};
export type RequirementAssessment = {
  party_requirements: PartyRequirement[];
  no_requirements_reason: string;
};
export const partyRequirementLimit = 20;
export const trimRequirementText = (value: string) =>
  value.replace(/^[\s\u001c-\u001f\u0085]+|[\s\u001c-\u001f\u0085]+$/gu, "");
export type ContextFields = {
  code: string;
  name: string;
  classification: string;
  category: string;
  relevance: ContextRelevance;
  description: string;
  requirements: string;
  evidence_summary: string;
  owner_user_id: string;
  review_due_on: string;
} & Partial<RequirementAssessment>;
export type ContextRecord = ContextFields & {
  id: string;
  tenant_id: string;
  unit_id: string;
  kind: ContextKind;
  status: ContextState;
  row_version: number;
  created_by_user_id: string;
  content_editor_user_id: string;
  updated_by_user_id: string;
  updated_at: string;
  reviewed_at: string | null;
  decision_note: string;
  owner_display_name?: string | null;
};
export type ContextRevision = { command: string; snapshot: ContextRecord };
export type ContextPermission = { read: boolean; manage: boolean; review: boolean; processRead: boolean };
export type ResponsiblePerson = { user_id: string; display_name: string };
export const contextPageSize = 25;
export const contextStates = ["draft", "active", "retired"] as const;
export const contextRelevance = ["under_review", "relevant", "not_relevant"] as const;
export const contextCategories = ["legal", "regulatory", "technology", "market", "culture", "social", "economic", "environmental", "strategic", "other"];
export const partyTypes = ["customer", "employee", "supplier", "regulator", "owner", "community", "other"];
const uuid = /^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i;
const date = /^\d{4}-\d{2}-\d{2}$/;
const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

export class ContextError extends Error {
  constructor(public readonly status: number, public readonly scopeChanged = false) {
    super("The context register request could not be verified.");
  }
}

function verifyScope(scope: ContextScope) {
  if (![scope.userId, scope.unitId, scope.tenantId].every(id => uuid.test(id))) {
    throw new ContextError(409, true);
  }
}

async function request(path: string, signal: AbortSignal, tenantId?: string, init?: RequestInit) {
  const response = await fetch("/api/identity" + path, {
    credentials: "include",
    cache: "no-store",
    signal: AbortSignal.any([signal, AbortSignal.timeout(15_000)]),
    ...init,
  });
  if (!response.ok) throw new ContextError(response.status);
  if (tenantId && response.headers.get("X-Tenant-ID") !== tenantId) {
    throw new ContextError(409, true);
  }
  const body: unknown = await response.json();
  signal.throwIfAborted();
  return body;
}

async function verifyIdentity(scope: ContextScope, signal: AbortSignal) {
  verifyScope(scope);
  const identity = await request("/auth/me", signal);
  if (!isObject(identity) || identity.id !== scope.userId || identity.current_tenant_id !== scope.tenantId) {
    throw new ContextError(409, true);
  }
}

export async function getContextPermissions(scope: ContextScope, signal: AbortSignal): Promise<ContextPermission> {
  await verifyIdentity(scope, signal);
  const value = await request("/qms-access/effective?unit_id=" + scope.unitId, signal);
  if (!isObject(value) || value.unit_id !== scope.unitId || !Array.isArray(value.capabilities)) {
    throw new ContextError(409, true);
  }
  await verifyIdentity(scope, signal);
  return {
    read: value.capabilities.includes("context.read"),
    manage: value.capabilities.includes("context.manage"),
    review: value.capabilities.includes("context.review"),
    processRead: value.capabilities.includes("processes.read"),
  };
}

function parseRecord(value: unknown, scope: ContextScope, kind: ContextKind): ContextRecord {
  if (!isObject(value) || value.tenant_id !== scope.tenantId || value.unit_id !== scope.unitId || value.kind !== kind) {
    throw new ContextError(409, true);
  }
  const bounds = { code: 40, name: 160, classification: 40, category: 20, description: 4000, requirements: 4000, evidence_summary: 4000, decision_note: 1000 };
  for (const [key, max] of Object.entries(bounds)) {
    const field = value[key];
    if (typeof field !== "string" || [...field].length > max) throw new ContextError(502);
  }
  if (!["id", "owner_user_id", "created_by_user_id", "content_editor_user_id", "updated_by_user_id"].every(
    key => typeof value[key] === "string" && uuid.test(value[key]),
  ) || !contextStates.some(state => state === value.status)
    || !contextRelevance.some(relevance => relevance === value.relevance)
    || typeof value.row_version !== "number" || !Number.isInteger(value.row_version) || value.row_version < 1
    || typeof value.review_due_on !== "string" || !date.test(value.review_due_on)
    || typeof value.updated_at !== "string" || !Number.isFinite(Date.parse(value.updated_at))
    || (value.owner_display_name != null && (typeof value.owner_display_name !== "string" || value.owner_display_name.length > 320))
    || (value.reviewed_at !== null && (typeof value.reviewed_at !== "string" || !Number.isFinite(Date.parse(value.reviewed_at))))
  ) throw new ContextError(502);
  const entries = value.party_requirements === undefined ? [] : value.party_requirements;
  const reason = value.no_requirements_reason === undefined ? "" : value.no_requirements_reason;
  if (!Array.isArray(entries) || entries.length > partyRequirementLimit || typeof reason !== "string"
    || [...reason].length > 600 || reason !== trimRequirementText(reason) || (entries.length > 0 && reason)
    || (kind !== "interested-parties" && (entries.length > 0 || reason))
    || !entries.every(isPartyRequirement) || new Set(entries.map(item => item.id)).size !== entries.length) {
    throw new ContextError(502);
  }
  return { ...value, party_requirements: entries, no_requirements_reason: reason } as ContextRecord;
}

function isPartyRequirement(value: unknown): value is PartyRequirement {
  if (!isObject(value) || typeof value.id !== "string" || !uuid.test(value.id)
    || value.id !== value.id.toLowerCase() || !requirementDispositions.some(item => item === value.disposition)) {
    return false;
  }
  const validText = (field: unknown, min: number, max: number) =>
    typeof field === "string" && field === trimRequirementText(field) && field.length >= min && [...field].length <= max;
  return validText(value.statement, 1, 360) && validText(value.source, 1, 200)
    && validText(value.rationale, value.disposition === "pending" ? 0 : 1, 600);
}

export function requirementReviewBlocker(entry: ContextRecord): string | null {
  if (entry.kind !== "interested-parties") return null;
  const items = entry.party_requirements ?? [];
  if (items.length === 0 && !entry.no_requirements_reason) return "Record the requirements assessment before review.";
  if (items.some(item => item.disposition === "pending")) return "Decide which requirements the QMS will address before review.";
  if (entry.relevance === "not_relevant" && items.some(item => item.disposition === "addressed_by_qms")) {
    return "A party with requirements addressed by the QMS must be relevant.";
  }
  return null;
}

export async function listContext(scope: ContextScope, kind: ContextKind, status: ContextState | "", offset: number, signal: AbortSignal) {
  await verifyIdentity(scope, signal);
  const query = new URLSearchParams({ unit_id: scope.unitId, limit: String(contextPageSize + 1), offset: String(offset) });
  if (status) query.set("status", status);
  const body = await request(`/context/${kind}?${query}`, signal, scope.tenantId);
  if (!Array.isArray(body) || body.length > contextPageSize + 1) throw new ContextError(502);
  const records = body.map(record => parseRecord(record, scope, kind));
  if (new Set(records.map(record => record.id)).size !== records.length || (status && records.some(record => record.status !== status))) {
    throw new ContextError(502);
  }
  await verifyIdentity(scope, signal);
  return { records: records.slice(0, contextPageSize), hasMore: records.length > contextPageSize };
}

export async function listResponsiblePeople(scope: ContextScope, offset: number, signal: AbortSignal): Promise<ResponsiblePerson[]> {
  await verifyIdentity(scope, signal);
  const body = await request(`/context/members?unit_id=${scope.unitId}&limit=100&offset=${offset}`, signal, scope.tenantId);
  if (!Array.isArray(body) || body.length > 100 || !body.every(person => isObject(person)
    && typeof person.user_id === "string" && uuid.test(person.user_id)
    && typeof person.display_name === "string" && person.display_name.length <= 320)) throw new ContextError(502);
  await verifyIdentity(scope, signal);
  return body;
}

export async function contextHistory(scope: ContextScope, entry: ContextRecord, before: number, signal: AbortSignal): Promise<ContextRevision[]> {
  await verifyIdentity(scope, signal);
  const body = await request(`/context/${entry.kind}/${entry.id}/history?unit_id=${scope.unitId}&before_version=${before}`, signal, scope.tenantId);
  if (!Array.isArray(body) || body.length > contextPageSize) throw new ContextError(502);
  const result = body.map((row: unknown) => {
    if (!isObject(row) || typeof row.command !== "string" || !["created", "updated", "reviewed", "retired"].includes(row.command)) {
      throw new ContextError(502);
    }
    const snapshot = parseRecord(row.snapshot, scope, entry.kind);
    if (snapshot.id !== entry.id || snapshot.row_version >= before) throw new ContextError(409, true);
    return { command: row.command, snapshot };
  });
  await verifyIdentity(scope, signal);
  return result;
}

type ProcessCandidate = { id: string; code: string; name: string; row_version: number };
export type PartyProcessLink = {
  id: string;
  requirement_id: string;
  process_id: string;
  requirement_snapshot: PartyRequirement;
  process_code: string;
  process_name: string;
  process_version: number;
  linked_party_version: number;
  rationale: string;
  created_at: string;
  removed_party_version: number | null;
  removed_at: string | null;
  removal_reason: string;
  requirement_current: boolean;
  process_state: "current" | "changed" | "archived" | "unavailable";
};
const processStates = ["current", "changed", "archived", "unavailable"];
const validUuid = (id: unknown): id is string => typeof id === "string" && uuid.test(id);
const positiveVersion = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value) && value > 0 && value <= 2147483647;
const processLabel = (value: unknown, limit: number) =>
  typeof value === "string" && value.length > 0 && [...value].length <= limit;
const processDate = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));

function processEnvelope(value: unknown, scope: ContextScope, record: ContextRecord, expectedVersion: number) {
  if (!isObject(value) || value.tenant_id !== scope.tenantId || value.unit_id !== scope.unitId || value.party_id !== record.id) {
    throw new ContextError(409, true);
  }
  if (value.party_version !== expectedVersion) throw new ContextError(409);
  return value;
}

async function processRequest(
  scope: ContextScope, record: ContextRecord, endpoint: string, query: URLSearchParams,
  signal: AbortSignal, version: number, init?: RequestInit,
) {
  await verifyIdentity(scope, signal);
  parseRecord(record, scope, "interested-parties");
  query.set("unit_id", scope.unitId);
  const raw = await request(
    `/context/interested-parties/${record.id}/${endpoint}?${query}`,
    signal, scope.tenantId, init,
  );
  const result = processEnvelope(raw, scope, record, version);
  await verifyIdentity(scope, signal);
  return result;
}

function processPage<T extends { id: string }>(
  value: Record<string, unknown>, validate: (item: unknown) => boolean,
) {
  const items = value.items;
  if (!Array.isArray(items) || items.length > contextPageSize || typeof value.has_more !== "boolean"
    || !items.every(validate) || new Set(items.map(item => item.id)).size !== items.length) {
    throw new ContextError(502);
  }
  return { items: items as T[], hasMore: value.has_more };
}

export async function partyProcessCandidates(
  scope: ContextScope, record: ContextRecord, search: string, offset: number, signal: AbortSignal,
) {
  const query = new URLSearchParams({ limit: String(contextPageSize), offset: String(offset), q: search });
  const result = await processRequest(scope, record, "process-candidates", query, signal, record.row_version);
  return processPage<ProcessCandidate>(result, item =>
    isObject(item) && validUuid(item.id) && processLabel(item.code, 40)
    && processLabel(item.name, 160) && positiveVersion(item.row_version),
  );
}

export async function partyProcessLinks(
  scope: ContextScope, record: ContextRecord, offset: number, signal: AbortSignal,
) {
  const query = new URLSearchParams({ limit: String(contextPageSize), offset: String(offset) });
  const result = await processRequest(scope, record, "process-links", query, signal, record.row_version);
  return processPage<PartyProcessLink>(result, item => {
    if (!isObject(item) || !validUuid(item.id) || !validUuid(item.requirement_id) || !validUuid(item.process_id)
      || !isPartyRequirement(item.requirement_snapshot) || item.requirement_snapshot.id !== item.requirement_id
      || item.requirement_snapshot.disposition !== "addressed_by_qms"
      || !processLabel(item.process_code, 40) || !processLabel(item.process_name, 160)
      || !positiveVersion(item.process_version) || !positiveVersion(item.linked_party_version)
      || item.linked_party_version > record.row_version || !processDate(item.created_at)
      || !processLabel(item.rationale, 600) || typeof item.requirement_current !== "boolean"
      || !processStates.some(state => state === item.process_state)) return false;
    if (item.removed_at === null) return item.removed_party_version === null && item.removal_reason === "";
    return processDate(item.removed_at) && positiveVersion(item.removed_party_version)
      && item.removed_party_version > item.linked_party_version && item.removed_party_version <= record.row_version
      && processLabel(item.removal_reason, 600);
  });
}

export type PartyProcessCommand =
  | { kind: "link"; requirementId: string; candidate: ProcessCandidate; rationale: string }
  | { kind: "remove"; linkId: string; reason: string };

export async function changePartyProcessLink(
  scope: ContextScope, record: ContextRecord, command: PartyProcessCommand, csrf: string, signal: AbortSignal,
) {
  if (!/^[A-Za-z0-9_-]{20,256}$/.test(csrf)) throw new ContextError(403);
  if (command.kind === "remove" && !validUuid(command.linkId)) throw new ContextError(422);
  const path = command.kind === "link" ? "process-links" : `process-links/${command.linkId}/remove`;
  const body = command.kind === "link" ? {
    requirement_id: command.requirementId, process_id: command.candidate.id,
    expected_process_version: command.candidate.row_version, rationale: command.rationale,
  } : { reason: command.reason };
  const result = await processRequest(scope, record, path, new URLSearchParams(), signal, record.row_version + 1, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify({ ...body, expected_party_version: record.row_version }),
  });
  if (!validUuid(result.link_id) || result.action !== (command.kind === "link" ? "linked" : "removed")
    || (command.kind === "remove" && result.link_id !== command.linkId)) throw new ContextError(502);
}

export type ContextCommand =
  | { action: "create"; fields: ContextFields }
  | { action: "edit"; entry: ContextRecord; fields: ContextFields }
  | { action: "review"; entry: ContextRecord; note: string; review_due_on: string }
  | { action: "retire"; entry: ContextRecord; note: string };

export async function saveContext(scope: ContextScope, kind: ContextKind, command: ContextCommand, csrf: string, signal: AbortSignal) {
  await verifyIdentity(scope, signal);
  if (!/^[A-Za-z0-9_-]{20,256}$/.test(csrf)) throw new ContextError(403);
  const base = "/context/" + kind;
  let path = base;
  let body: object;
  if (command.action === "create") {
    body = { ...command.fields, unit_id: scope.unitId };
  } else {
    parseRecord(command.entry, scope, kind);
    const suffix = command.action === "edit" ? "" : "/" + command.action;
    path = `${base}/${command.entry.id}${suffix}?unit_id=${scope.unitId}`;
    const expected_version = command.entry.row_version;
    if (command.action === "edit") body = { ...command.fields, expected_version };
    else if (command.action === "review") body = { note: command.note, review_due_on: command.review_due_on, expected_version };
    else body = { note: command.note, expected_version };
  }
  const raw = await request(path, signal, scope.tenantId, {
    method: command.action === "edit" ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: JSON.stringify(body),
  });
  const result = parseRecord(raw, scope, kind);
  const expectedState = command.action === "review" ? "active" : command.action === "retire" ? "retired" : "draft";
  if (result.status !== expectedState || result.updated_by_user_id !== scope.userId
    || (command.action === "create" ? result.row_version !== 1
      : result.id !== command.entry.id || result.row_version !== command.entry.row_version + 1)) {
    throw new ContextError(502);
  }
  const assessment = command.action === "create" ? command.fields
    : command.action === "edit" ? { ...command.entry, ...command.fields } : command.entry;
  const received = result.party_requirements ?? [];
  const sent = assessment.party_requirements ?? [];
  if ((result.no_requirements_reason ?? "") !== (assessment.no_requirements_reason ?? "")
    || sent.length !== received.length || sent.some((item, i) => {
      const actual = received[i];
      return item.id !== actual.id || item.statement !== actual.statement || item.source !== actual.source
        || item.disposition !== actual.disposition || item.rationale !== actual.rationale;
    })) throw new ContextError(502);
  await verifyIdentity(scope, signal);
  return result;
}
