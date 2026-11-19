export type GuideResource = "processes" | "documents" | "implementations" | "risks" | "nonconformities" | "capas" | "audits";
export type GuideUnit = { id: string; code: string; name: string };
export type GuideRecord = { id: string; code: string; name: string; state: string; qualified: boolean };
export type ResourceObservation = { kind: "loaded"; records: GuideRecord[]; limited: boolean } | { kind: "restricted" | "unavailable" };
export type GuideSnapshot = { tenantId: string; userId: string; unitId: string; fetchedAt: string; resources: Record<GuideResource, ResourceObservation> };
export class GuideAccessError extends Error {
  constructor(public status: number) { super("The guide context could not be verified."); this.name = "GuideAccessError"; }
}

type Context = { tenantId: string; userId: string; unitId: string };
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const uuid = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const label = (value: unknown, max: number): value is string => typeof value === "string" && value.trim().length > 0 && value.length <= max;
const member = (value: unknown, choices: readonly string[]): value is string => typeof value === "string" && choices.includes(value);
const uniqueIds = (rows: { id: string }[]) => new Set(rows.map(row => row.id.toLowerCase())).size === rows.length;
const invalid = () => new GuideAccessError(409);
const unavailable = () => new Error("Guide data could not be verified.");
const documentCapabilities = ["documents.read", "documents.author", "documents.review", "documents.approve", "documents.release", "documents.obsolete"];
const knownCapabilities = new Set([...documentCapabilities, "evidence.read", "evidence.create", "evidence.review", "processes.read", "processes.manage", "controls.read", "controls.manage", "control_instances.read", "control_instances.manage", "risks.read", "risks.manage", "risks.review", "ncr.read", "ncr.manage", "ncr.review", "capa.read", "capa.manage", "capa.review", "audits.read", "audits.manage", "audits.execute", "audits.review", "projects.read", "projects.manage"]);

function checkAbort(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("The guide read was cancelled.", "AbortError");
}

async function read(path: string, signal: AbortSignal | undefined, request: typeof fetch, tenantHeader?: string): Promise<unknown> {
  checkAbort(signal);
  try {
    const response = await request(`/api/identity${path}`, { credentials: "include", cache: "no-store", signal });
    checkAbort(signal);
    if (response.status === 401 || response.status === 403) throw new GuideAccessError(response.status);
    if (!response.ok) throw unavailable();
    if (tenantHeader && response.headers.get("X-Tenant-ID") !== tenantHeader) throw invalid();
    const body: unknown = await response.json();
    checkAbort(signal);
    return body;
  } catch (cause) {
    checkAbort(signal);
    if (cause instanceof GuideAccessError) throw cause;
    if (cause instanceof Error && cause.name === "AbortError") throw new DOMException("The guide read was cancelled.", "AbortError");
    throw unavailable();
  }
}

async function checkIdentity(tenantId: string, userId: string | undefined, signal: AbortSignal | undefined, request: typeof fetch): Promise<string> {
  const identity = await read("/auth/me", signal, request);
  if (!object(identity) || !uuid(identity.id) || identity.current_tenant_id !== tenantId || (userId !== undefined && identity.id !== userId)) throw invalid();
  return identity.id;
}

function validUnit(value: unknown, tenantId: string): value is Record<string, unknown> & GuideUnit & { status: string } {
  return object(value) && uuid(value.id) && value.tenant_id === tenantId && label(value.code, 40) && label(value.name, 160)
    && member(value.status, ["active", "archived"]) && member(value.unit_type, ["site", "department", "team"]);
}

/** First page only: a full page is a lower bound, never an enterprise total. */
export async function loadGuideUnits(tenantId: string, signal?: AbortSignal, request: typeof fetch = fetch): Promise<{ units: GuideUnit[]; limited: boolean }> {
  checkAbort(signal);
  if (!uuid(tenantId)) throw invalid();
  const userId = await checkIdentity(tenantId, undefined, signal, request);
  const rows = await read("/organization/units?limit=100&offset=0", signal, request, tenantId);
  if (!Array.isArray(rows) || rows.length > 100 || !rows.every(row => validUnit(row, tenantId)) || !uniqueIds(rows)) throw invalid();
  await checkIdentity(tenantId, userId, signal, request);
  checkAbort(signal);
  return { units: rows.filter(row => row.status === "active").map(({ id, code, name }) => ({ id, code, name })), limited: rows.length === 100 };
}

const resources: { kind: GuideResource; path: string; allowed: (caps: Set<string>) => boolean }[] = [
  { kind: "processes", path: "/processes", allowed: caps => caps.has("processes.read") },
  { kind: "documents", path: "/documents", allowed: caps => documentCapabilities.some(cap => caps.has(cap)) },
  { kind: "implementations", path: "/control-instances", allowed: caps => caps.has("control_instances.read") && caps.has("controls.read") },
  { kind: "risks", path: "/risks", allowed: caps => caps.has("risks.read") },
  { kind: "nonconformities", path: "/nonconformities", allowed: caps => caps.has("ncr.read") },
  { kind: "capas", path: "/capas", allowed: caps => caps.has("capa.read") },
  { kind: "audits", path: "/internal-audits/audits", allowed: caps => caps.has("audits.read") },
];
const states: Record<GuideResource, readonly string[]> = {
  processes: ["active", "archived"], documents: ["draft", "active", "obsolete"],
  implementations: ["not_started", "in_progress", "evidence_required", "under_review", "implemented", "not_applicable"],
  risks: ["draft", "assessed", "action_required", "monitoring", "closed"],
  nonconformities: ["draft", "open", "containment", "investigation", "action_required", "verification", "closed", "cancelled"],
  capas: ["draft", "analysis", "action_planned", "implementation", "effectiveness_review", "effective", "closed", "cancelled"],
  audits: ["draft", "planned", "ready", "in_progress", "reporting", "completed", "cancelled"],
};

function record(value: unknown, kind: GuideResource, context: Context): GuideRecord {
  // The process and implementation response contracts omit tenant_id; unit_id is mandatory in every schema.
  const tenantRequired = kind !== "processes" && kind !== "implementations";
  if (!object(value) || !uuid(value.id) || value.unit_id !== context.unitId
    || (tenantRequired || "tenant_id" in value) && value.tenant_id !== context.tenantId
    || !label(value.code, kind === "implementations" ? 50 : 40)) throw unavailable();
  const name = kind === "documents" ? value.title : value.name;
  if (!label(name, kind === "documents" ? 200 : 160)) throw unavailable();
  const state = kind === "implementations" ? value.implementation_status : kind === "processes" || kind === "documents" ? value.status : value.state;
  if (!member(state, states[kind])) throw unavailable();
  let qualified = false;
  if (kind === "implementations") {
    if (!member(value.status, ["active", "archived"])) throw unavailable();
    qualified = state === "implemented" && value.status === "active";
  } else if (kind === "documents") {
    if (value.current_revision_id !== null && !uuid(value.current_revision_id)) throw unavailable();
    // Record metadata only: the reader does not inspect revision approval, file content or PDF safety.
    qualified = state === "active" && value.current_revision_id !== null;
  } else if (kind === "processes") qualified = state === "active";
  else if (kind !== "audits") qualified = state === "closed";
  // Audit execution is not implemented; a record never proves an executed audit or readiness.
  return { id: value.id, code: value.code, name, state: kind === "implementations" && value.status === "archived" ? `${state} (archived)` : state, qualified };
}

/** Unit observations only. No record count completes a project, requirement or ISO assessment. */
export async function loadGuideSnapshot(context: Context, signal?: AbortSignal, request: typeof fetch = fetch): Promise<GuideSnapshot> {
  checkAbort(signal);
  if (![context.tenantId, context.userId, context.unitId].every(uuid)) throw invalid();
  await checkIdentity(context.tenantId, context.userId, signal, request);
  const unit = await read(`/organization/units/${context.unitId}`, signal, request);
  if (!validUnit(unit, context.tenantId) || unit.id !== context.unitId || unit.status !== "active") throw invalid();
  const access = await read(`/qms-access/effective?unit_id=${context.unitId}`, signal, request);
  if (!object(access) || access.unit_id !== context.unitId || !Array.isArray(access.capabilities)
    || !access.capabilities.every(cap => typeof cap === "string" && knownCapabilities.has(cap))
    || new Set(access.capabilities).size !== access.capabilities.length) throw invalid();
  const caps = new Set<string>(access.capabilities);
  const observations = {} as Record<GuideResource, ResourceObservation>;
  // Sequential reads stop immediately when access is revoked; no partial snapshot escapes.
  for (const resource of resources) {
    checkAbort(signal);
    if (!resource.allowed(caps)) { observations[resource.kind] = { kind: "restricted" }; continue; }
    try {
      const rows = await read(`${resource.path}?unit_id=${context.unitId}&limit=50&offset=0`, signal, request);
      // Documents return limit+1 as a pagination sentinel; validate it before trimming the display sample.
      const maxRows = resource.kind === "documents" ? 51 : 50;
      if (!Array.isArray(rows) || rows.length > maxRows) throw unavailable();
      const records = rows.map(row => record(row, resource.kind, context));
      if (!uniqueIds(records)) throw unavailable();
      observations[resource.kind] = { kind: "loaded", records: records.slice(0, 50), limited: rows.length >= 50 };
    } catch (cause) {
      checkAbort(signal);
      if (cause instanceof GuideAccessError || cause instanceof Error && cause.name === "AbortError") throw cause;
      observations[resource.kind] = { kind: "unavailable" };
    }
  }
  await checkIdentity(context.tenantId, context.userId, signal, request);
  checkAbort(signal);
  return { ...context, fetchedAt: new Date().toISOString(), resources: observations };
}
