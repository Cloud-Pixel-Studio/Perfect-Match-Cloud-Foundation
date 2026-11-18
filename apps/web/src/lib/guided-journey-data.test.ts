import { describe, expect, it } from "vitest";

import { GuideAccessError, loadGuideSnapshot, loadGuideUnits, type GuideResource } from "./guided-journey-data";

const tenantId = "10000000-0000-4000-8000-000000000001";
const userId = "20000000-0000-4000-8000-000000000001";
const unitId = "30000000-0000-4000-8000-000000000001";
const otherId = "90000000-0000-4000-8000-000000000001";
const context = { tenantId, userId, unitId };
const unit = { id: unitId, tenant_id: tenantId, code: "LAB", name: "Laboratory", status: "active", unit_type: "department" };
const identity = { id: userId, current_tenant_id: tenantId };
const paths: Record<GuideResource, string> = { processes: "/processes", documents: "/documents", implementations: "/control-instances", risks: "/risks", nonconformities: "/nonconformities", capas: "/capas", audits: "/internal-audits/audits" };
const capabilities = ["processes.read", "documents.read", "controls.read", "control_instances.read", "risks.read", "ncr.read", "capa.read", "audits.read"];
const row = (extra: Record<string, unknown> = {}) => ({ id: "40000000-0000-4000-8000-000000000001", tenant_id: tenantId, unit_id: unitId, code: "REC-001", name: "Example", ...extra });
const sample: Record<GuideResource, unknown[]> = {
  processes: [row({ tenant_id: undefined, status: "active" })],
  documents: [row({ title: "Procedure", status: "active", current_revision_id: otherId })],
  implementations: [row({ tenant_id: undefined, status: "active", implementation_status: "implemented" })],
  risks: [row({ state: "monitoring" })], nonconformities: [row({ state: "open" })], capas: [row({ state: "draft" })], audits: [row({ state: "planned" })],
};
type Options = { caps?: unknown; rows?: Partial<Record<GuideResource, unknown>>; units?: unknown; unitBody?: unknown; tenantHeader?: string | null; before?: unknown; after?: unknown; response?: (path: string) => Response | undefined; afterResponse?: (path: string) => void };
function fixture(options: Options = {}) {
  const calls: { url: string; options?: RequestInit }[] = [];
  let identityReads = 0;
  const request: typeof fetch = async (url, init) => {
    const full = String(url); const path = full.replace("/api/identity", "");
    calls.push({ url: full, options: init });
    let response = options.response?.(path);
    if (!response) {
      let body: unknown;
      if (path === "/auth/me") body = identityReads++ === 0 ? options.before ?? identity : options.after ?? identity;
      else if (path.startsWith("/organization/units?")) body = options.units ?? [unit];
      else if (path === `/organization/units/${unitId}`) body = options.unitBody ?? unit;
      else if (path.startsWith("/qms-access/effective?")) body = options.caps ?? { unit_id: unitId, capabilities };
      else { const kind = (Object.keys(paths) as GuideResource[]).find(key => path.startsWith(`${paths[key]}?`)); body = kind ? options.rows?.[kind] ?? sample[kind] : undefined; }
      if (body === undefined) throw new Error(`Unexpected route ${path}`);
      response = Response.json(body, { headers: path.startsWith("/organization/units?") && options.tenantHeader !== null ? { "X-Tenant-ID": options.tenantHeader ?? tenantId } : {} });
    }
    options.afterResponse?.(path);
    return response;
  };
  return { request, calls };
}

describe("guide unit reads", () => {
  it("reads an authenticated, tenant-verified bounded page and preserves the abort signal", async () => {
    const f = fixture(); const signal = new AbortController().signal;
    expect(await loadGuideUnits(tenantId, signal, f.request)).toEqual({ units: [{ id: unitId, code: "LAB", name: "Laboratory" }], limited: false });
    expect(f.calls.map(call => call.url)).toEqual(["/api/identity/auth/me", "/api/identity/organization/units?limit=100&offset=0", "/api/identity/auth/me"]);
    for (const call of f.calls) expect(call.options).toEqual({ credentials: "include", cache: "no-store", signal });
  });
  it("marks a full first page as limited and filters archived units", async () => {
    const units = Array.from({ length: 100 }, (_, i) => ({ ...unit, id: `30000000-0000-4000-8000-${String(i).padStart(12, "0")}`, status: i ? "active" : "archived" }));
    const f = fixture({ units }); const result = await loadGuideUnits(tenantId, undefined, f.request);
    expect(result.limited).toBe(true); expect(result.units).toHaveLength(99);
  });
  it.each([
    { tenantHeader: null }, { tenantHeader: otherId }, { units: [{ ...unit, tenant_id: otherId }] }, { units: [unit, unit] }, { units: [{ ...unit, id: "../escape" }] }, { units: [{ ...unit, status: ["active"] }] }, { units: [{ ...unit, name: "" }] }, { units: {} }, { units: Array.from({ length: 101 }, () => unit) },
    { before: { ...identity, current_tenant_id: otherId } }, { after: { ...identity, id: otherId } }, { after: { ...identity, current_tenant_id: otherId } },
  ])("rejects invalid or stale unit context: %j", async options => {
    const f = fixture(options); await expect(loadGuideUnits(tenantId, undefined, f.request)).rejects.toMatchObject({ status: 409 });
  });
});

describe("guide snapshots", () => {
  it("reads seven permitted bounded resources after verifying selected unit and effective capabilities", async () => {
    const f = fixture(); const signal = new AbortController().signal;
    const result = await loadGuideSnapshot(context, signal, f.request);
    expect(result).toMatchObject(context); expect(Number.isFinite(Date.parse(result.fetchedAt))).toBe(true);
    expect(f.calls.slice(0, 3).map(c => c.url)).toEqual(["/api/identity/auth/me", `/api/identity/organization/units/${unitId}`, `/api/identity/qms-access/effective?unit_id=${unitId}`]);
    for (const [kind, path] of Object.entries(paths)) {
      expect(f.calls.some(c => c.url === `/api/identity${path}?unit_id=${unitId}&limit=50&offset=0`)).toBe(true);
      expect(result.resources[kind as GuideResource]).toMatchObject({ kind: "loaded", limited: false });
    }
    for (const call of f.calls) expect(call.options).toEqual({ credentials: "include", cache: "no-store", signal });
    expect(f.calls.at(-1)?.url).toBe("/api/identity/auth/me");
  });
  it.each([{ caps: [] }, { caps: ["control_instances.read"] }, { caps: ["controls.read"] }])("never requests denied modules or tenant-wide union capabilities: %j", async ({ caps }) => {
    const f = fixture({ caps: { unit_id: unitId, capabilities: caps } });
    const result = await loadGuideSnapshot(context, undefined, f.request);
    expect(Object.values(result.resources).every(resource => resource.kind === "restricted")).toBe(true);
    expect(f.calls).toHaveLength(4);
    expect(f.calls.some(c => c.url.includes("active-capabilities"))).toBe(false);
  });
  it("honors document author capability without granting other modules", async () => {
    const f = fixture({ caps: { unit_id: unitId, capabilities: ["documents.author"] } });
    const result = await loadGuideSnapshot(context, undefined, f.request);
    expect(result.resources.documents.kind).toBe("loaded"); expect(result.resources.processes.kind).toBe("restricted");
  });
  it.each([
    { unitBody: { ...unit, tenant_id: otherId } }, { unitBody: { ...unit, id: otherId } }, { unitBody: { ...unit, status: "archived" } },
    { caps: { unit_id: otherId, capabilities } }, { caps: { unit_id: unitId, capabilities: ["processes.read", "processes.read"] } }, { caps: { unit_id: unitId, capabilities: [["processes.read"]] } },
    { before: { ...identity, id: otherId } }, { after: { ...identity, id: otherId } }, { after: { ...identity, current_tenant_id: otherId } },
  ])("rejects invalid snapshot context: %j", async options => { const f = fixture(options); await expect(loadGuideSnapshot(context, undefined, f.request)).rejects.toMatchObject({ status: 409 }); });
  it.each([401, 403])("invalidates the complete snapshot on HTTP %s from any read", async status => {
    for (const target of ["/auth/me", `/organization/units/${unitId}`, "/qms-access/effective", ...Object.values(paths)]) {
      const f = fixture({ response: path => path.split("?")[0] === target ? Response.json({ detail: "secret diagnostic" }, { status }) : undefined });
      await expect(loadGuideSnapshot(context, undefined, f.request)).rejects.toMatchObject({ status });
      await expect(loadGuideSnapshot(context, undefined, f.request)).rejects.toBeInstanceOf(GuideAccessError);
    }
  });
  it.each(Object.keys(paths) as GuideResource[])("rejects malformed, duplicate and wrong-scope %s records without returning partial rows", async kind => {
    for (const bad of [{ ...sample[kind][0] as object, unit_id: otherId }, { ...sample[kind][0] as object, tenant_id: otherId }, { ...sample[kind][0] as object, id: "bad" }, { ...sample[kind][0] as object, code: null }, { ...sample[kind][0] as object, name: null, title: null }, { ...sample[kind][0] as object, state: ["closed"], status: ["active"] }]) {
      const f = fixture({ rows: { [kind]: [sample[kind][0], bad] } });
      expect((await loadGuideSnapshot(context, undefined, f.request)).resources[kind]).toEqual({ kind: "unavailable" });
    }
    const f = fixture({ rows: { [kind]: [sample[kind][0], sample[kind][0]] } });
    expect((await loadGuideSnapshot(context, undefined, f.request)).resources[kind]).toEqual({ kind: "unavailable" });
  });
  it.each(["documents", "risks", "nonconformities", "capas", "audits"] as GuideResource[])("requires tenant_id in actual %s schemas", async kind => {
    const bad = { ...sample[kind][0] as Record<string, unknown> }; delete bad.tenant_id;
    const f = fixture({ rows: { [kind]: [bad] } }); expect((await loadGuideSnapshot(context, undefined, f.request)).resources[kind]).toEqual({ kind: "unavailable" });
  });
  it("keeps server/network/JSON errors unavailable and still checks identity after a partial error", async () => {
    for (const response of [() => Response.json({ detail: "private" }, { status: 500 }), () => new Response("bad json"), () => { throw new Error("private"); }]) {
      const f = fixture({ response: path => path.startsWith("/documents?") ? response() : undefined });
      const result = await loadGuideSnapshot(context, undefined, f.request);
      expect(result.resources.documents).toEqual({ kind: "unavailable" }); expect(result.resources.processes.kind).toBe("loaded");
      expect(JSON.stringify(result)).not.toContain("private");
    }
    const f = fixture({ after: { ...identity, id: otherId }, response: path => path.startsWith("/documents?") ? new Response("", { status: 500 }) : undefined });
    await expect(loadGuideSnapshot(context, undefined, f.request)).rejects.toThrow();
  });
  it("distinguishes empty observations from a first50 sample and rejects oversized pages", async () => {
    const f = fixture({ rows: { processes: [], risks: Array.from({ length: 50 }, (_, i) => row({ id: `40000000-0000-4000-8000-${String(i).padStart(12, "0")}`, state: "draft" })), capas: Array.from({ length: 51 }, () => row({ state: "draft" })) } });
    const result = await loadGuideSnapshot(context, undefined, f.request);
    expect(result.resources.processes).toEqual({ kind: "loaded", records: [], limited: false });
    expect(result.resources.risks).toMatchObject({ kind: "loaded", limited: true }); expect(result.resources.capas).toEqual({ kind: "unavailable" });
  });
  it.each([50, 51])("shows the first50 documents when the API returns %s rows including its optional sentinel", async count => {
    const documents = Array.from({ length: count }, (_, i) => row({ id: `40000000-0000-4000-8000-${String(i).padStart(12, "0")}`, title: `Procedure ${i}`, status: "active", current_revision_id: otherId }));
    const f = fixture({ rows: { documents } });
    const result = (await loadGuideSnapshot(context, undefined, f.request)).resources.documents;
    expect(result).toMatchObject({ kind: "loaded", limited: true });
    if (result.kind !== "loaded") throw new Error("Expected loaded document sample");
    expect(result.records).toHaveLength(50);
    expect(result.records.at(-1)?.name).toBe("Procedure 49");
    expect(result.records.some(record => record.name === "Procedure 50")).toBe(false);
  });
  it.each(["tenant", "unit", "duplicate", "malformed", "oversized"])("rejects the entire document observation if its sentinel is %s", async problem => {
    const documents = Array.from({ length: problem === "oversized" ? 52 : 51 }, (_, i) => row({ id: `40000000-0000-4000-8000-${String(i).padStart(12, "0")}`, title: `Procedure ${i}`, status: "active", current_revision_id: otherId }));
    if (problem === "tenant") documents[50] = { ...documents[50], tenant_id: otherId };
    if (problem === "unit") documents[50] = { ...documents[50], unit_id: otherId };
    if (problem === "duplicate") documents[50] = { ...documents[0] };
    if (problem === "malformed") documents[50] = { ...documents[50], id: "invalid" };
    const f = fixture({ rows: { documents } });
    expect((await loadGuideSnapshot(context, undefined, f.request)).resources.documents).toEqual({ kind: "unavailable" });
  });
  it("qualifies only explicit record states, keeping implementation archive and draft distinctions", async () => {
    const variants = (extra: Record<string, unknown>[]) => extra.map((v, i) => row({ id: `40000000-0000-4000-8000-${String(i).padStart(12, "0")}`, ...v }));
    const f = fixture({ rows: {
      processes: variants([{ status: "active" }, { status: "archived" }]),
      documents: variants([{ title: "A", status: "active", current_revision_id: otherId }, { title: "B", status: "active", current_revision_id: null }, { title: "C", status: "draft", current_revision_id: otherId }]),
      implementations: variants([{ status: "active", implementation_status: "implemented" }, { status: "archived", implementation_status: "implemented" }, { status: "active", implementation_status: "under_review" }, { status: "active", implementation_status: "not_applicable" }]),
      risks: variants([{ state: "monitoring" }, { state: "closed" }]), nonconformities: variants([{ state: "closed" }, { state: "cancelled" }]), capas: variants([{ state: "effective" }, { state: "closed" }]), audits: variants([{ state: "planned" }, { state: "completed" }]),
    } });
    const resources = (await loadGuideSnapshot(context, undefined, f.request)).resources;
    const flags = (kind: GuideResource) => resources[kind].kind === "loaded" ? resources[kind].records.map(r => r.qualified) : [];
    expect(flags("processes")).toEqual([true, false]); expect(flags("documents")).toEqual([true, false, false]); expect(flags("implementations")).toEqual([true, false, false, false]); expect(flags("risks")).toEqual([false, true]); expect(flags("nonconformities")).toEqual([true, false]); expect(flags("capas")).toEqual([false, true]); expect(flags("audits")).toEqual([false, false]);
  });
  it.each(Object.keys(paths) as GuideResource[])("accepts API maximum code and display-name lengths for %s", async kind => {
    const code = "C".repeat(kind === "implementations" ? 50 : 40);
    const name = "N".repeat(kind === "documents" ? 200 : 160);
    const f = fixture({ rows: { [kind]: [{ ...sample[kind][0] as object, code, [kind === "documents" ? "title" : "name"]: name }] } });
    expect((await loadGuideSnapshot(context, undefined, f.request)).resources[kind]).toMatchObject({ kind: "loaded", records: [{ code, name }] });
  });
  it("accepts the actual action_planned CAPA state and rejects an invented planned state", async () => {
    const valid = fixture({ rows: { capas: [row({ state: "action_planned" })] } });
    expect((await loadGuideSnapshot(context, undefined, valid.request)).resources.capas).toMatchObject({ kind: "loaded", records: [{ state: "action_planned", qualified: false }] });
    const invalid = fixture({ rows: { capas: [row({ state: "planned" })] } });
    expect((await loadGuideSnapshot(context, undefined, invalid.request)).resources.capas).toEqual({ kind: "unavailable" });
  });
  it("invalidates all collected resources when the final identity check expires", async () => {
    let reads = 0;
    const f = fixture({ response: path => path === "/auth/me" && ++reads === 2 ? new Response("", { status: 401 }) : undefined });
    await expect(loadGuideSnapshot(context, undefined, f.request)).rejects.toMatchObject({ status: 401 });
    expect(f.calls.some(call => call.url.includes("/internal-audits/audits?"))).toBe(true);
  });
  it("checks cancellation after JSON parsing resolves late", async () => {
    const controller = new AbortController();
    const f = fixture({ response: path => path.startsWith("/documents?") ? {
      ok: true, status: 200, headers: new Headers(), json: async () => { controller.abort(); return sample.documents; },
    } as Response : undefined });
    await expect(loadGuideSnapshot(context, controller.signal, f.request)).rejects.toMatchObject({ name: "AbortError" });
  });
  it("rejects invalid revision and implementation enums", async () => {
    const f = fixture({ rows: { documents: [row({ title: "A", status: "active", current_revision_id: "unsafe" })], implementations: [row({ status: "active", implementation_status: ["implemented"] })] } });
    const resources = (await loadGuideSnapshot(context, undefined, f.request)).resources;
    expect(resources.documents.kind).toBe("unavailable"); expect(resources.implementations.kind).toBe("unavailable");
  });
  it("rejects unsafe inputs before any URL is requested", async () => {
    const f = fixture();
    for (const field of ["tenantId", "userId", "unitId"]) await expect(loadGuideSnapshot({ ...context, [field]: "../unsafe?" }, undefined, f.request)).rejects.toMatchObject({ status: 409 });
    await expect(loadGuideUnits("../unsafe?", undefined, f.request)).rejects.toMatchObject({ status: 409 }); expect(f.calls).toHaveLength(0);
  });
  it("rejects pre-aborted and late-aborted reads even when transport ignores the signal", async () => {
    const pre = new AbortController(); pre.abort(); const f = fixture();
    await expect(loadGuideSnapshot(context, pre.signal, f.request)).rejects.toMatchObject({ name: "AbortError" }); expect(f.calls).toHaveLength(0);
    for (const target of ["/auth/me", "/documents?", "/organization/units?"]) {
      const controller = new AbortController(); let reads = 0;
      const late = fixture({ afterResponse: path => { if (path.startsWith(target) && (target !== "/auth/me" || ++reads === 2)) controller.abort(); } });
      const pending = target === "/organization/units?" ? loadGuideUnits(tenantId, controller.signal, late.request) : loadGuideSnapshot(context, controller.signal, late.request);
      await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    }
  });
});
