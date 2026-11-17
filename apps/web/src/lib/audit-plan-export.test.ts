import { describe, expect, it, vi } from "vitest";
import { auditPlanFilename, collectAuditPlan, PlanExportError, renderAuditPlan } from "./audit-plan-export";

const id = (n: number) => `a0000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const selection = { id: id(1), unit_id: id(2), row_version: 7 };
const audit = { ...selection, tenant_id: id(3), code: "AUD-001", name: "Receiving audit", objective: "Verify receiving", scope_summary: "Records and controls", state: "planned", audit_type: "process", planned_start: "2026-11-20", planned_end: "2026-11-21", lead_auditor_user_id: id(5) };
const identity = { id: id(4), current_tenant_id: id(3) };
const common = { audit_id: selection.id, unit_id: selection.unit_id, row_version: 1, status: "active", withdrawal_reason: "", sequence: 10 };
const scope = { ...common, id: id(10), title: "Receiving", description: "Controlled records", process_id: null };
const criterion = { ...common, id: id(11), title: "Records", requirement: "Verify traceability", source_type: "internal", reference: "REC-01", scope_id: scope.id };
const member = { ...common, id: id(12), user_id: id(5), display_name_snapshot: "Alex Rivera", team_role: "auditor", responsibilities: "Review receiving evidence" };
const agenda = { ...common, id: id(13), title: "Receiving walkthrough", objective: "Observe traceability", method: "Interview", location: "Site one", starts_at: "2026-11-20T14:00:00Z", ends_at: "2026-11-20T15:00:00Z", scope_id: scope.id, auditor_team_member_id: member.id, auditee_team_member_id: null };
type Kind = "scopes" | "criteria" | "team" | "agenda";
function fixture(change?: (path: string, count: number) => unknown) {
  const data: Record<Kind, Record<string, unknown>[]> = { scopes: [{ ...scope }], criteria: [{ ...criterion }], team: [{ ...member }], agenda: [{ ...agenda }] };
  const counts = new Map<string, number>();
  const reader = vi.fn(async (input: string, init: RequestInit) => {
    expect(init.credentials).toBe("include"); expect(init.cache).toBe("no-store");
    expect(init.method).toBeUndefined();
    const url = new URL(input, "http://localhost");
    const path = url.pathname.replace("/api/identity", "");
    const count = (counts.get(path) ?? 0) + 1; counts.set(path, count);
    const override = change?.(path, count);
    if (override instanceof Response) return override;
    if (override !== undefined) return Response.json(override);
    if (path === "/auth/me") return Response.json(identity);
    if (path === "/auth/tenants") return Response.json([{ id: id(3), name: "Atlas Manufacturing" }, { id: id(99), name: "Other company must not export" }]);
    if (path.endsWith(selection.id)) return Response.json(audit);
    const endpoint = path.split("/").at(-1);
    const kind = (endpoint === "team-members" ? "team" : endpoint) as Kind;
    const offset = Number(url.searchParams.get("offset"));
    expect(url.searchParams.get("limit")).toBe("50");
    return Response.json(data[kind].slice(offset, offset + 50));
  });
  return { data, reader, collect: (controller = new AbortController()) => collectAuditPlan(selection, "HQ · Main site", controller.signal, reader) };
}

describe("audit planning download", () => {
  it("collects every page beyond the visible register, binds identity and rereads the parent", async () => {
    const f = fixture(); f.data.scopes = Array.from({ length: 51 }, (_, n) => ({ ...scope, id: n === 0 ? scope.id : id(100 + n) }));
    const plan = await f.collect();
    expect(f.reader.mock.calls.some(([url]) => url.includes("/team-members?limit=50"))).toBe(true);
    expect(f.reader.mock.calls.some(([url]) => url.includes("/team?"))).toBe(false);
    expect(plan.scopes).toHaveLength(51); expect(plan.company).toBe("Atlas Manufacturing");
    expect(f.reader.mock.calls.some(([url]) => url.endsWith("scopes?limit=50&offset=50"))).toBe(true);
    expect(f.reader.mock.calls.filter(([url]) => url.endsWith(selection.id))).toHaveLength(2);
    const html = renderAuditPlan(plan);
    expect(html).toContain("Planning copy · Not an issued audit report");
    expect(html).toContain("Alex Rivera"); expect(html).toContain("14:00:00 UTC");
    expect(html).not.toContain("Other company must not export");
  });
  it("includes withdrawals with reasons rather than silently omitting them", async () => {
    const f = fixture(); f.data.criteria[0] = { ...criterion, status: "withdrawn", withdrawal_reason: "Replaced by approved criterion" };
    const html = renderAuditPlan(await f.collect());
    expect(html).toContain("0 active · 1 withdrawn"); expect(html).toContain("Replaced by approved criterion");
  });
  it("renders empty planning sections without implying readiness or completion", async () => {
    const f = fixture(); for (const k of Object.keys(f.data) as Kind[]) f.data[k] = [];
    const html = renderAuditPlan(await f.collect());
    expect(html).toContain("No items recorded."); expect(html).toContain("Not assigned to an active planned auditor");
    expect(html).toContain("does not confirm readiness");
  });
  it("escapes customer text, blocks active content and creates a safe filename", async () => {
    const payload = '</style><script>alert(1)</script><img src=x onerror="fetch(1)">';
    const f = fixture(path => path.endsWith(selection.id) ? { ...audit, name: payload, code: "../bad/code" } : undefined);
    f.data.criteria[0].requirement = payload;
    const plan = await f.collect(); plan.unit = payload;
    const html = renderAuditPlan(plan);
    expect(html).not.toContain("<script>"); expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;"); expect(html).toContain("default-src 'none'");
    expect(html).not.toContain('src="http'); expect(html).not.toContain('<form');
    expect(auditPlanFilename(plan)).toMatch(/^PerfectMatch-plan-[A-Za-z0-9_-]+-v7\.html$/);
  });
  it.each(["scopes", "criteria", "team", "agenda"] as Kind[])("rejects a foreign audit/unit in %s", async kind => {
    const f = fixture(); f.data[kind][0] = { ...f.data[kind][0], unit_id: id(99) };
    await expect(f.collect()).rejects.toThrow("could not be verified");
  });
  it("rejects duplicate IDs instead of exporting duplicated pagination", async () => {
    const f = fixture(); f.data.scopes.push({ ...scope });
    await expect(f.collect()).rejects.toThrow("could not be verified");
  });
  it("rejects a partial oversized response", async () => {
    const f = fixture(path => path.endsWith("/scopes") ? Array.from({ length: 51 }, () => scope) : undefined);
    await expect(f.collect()).rejects.toThrow("could not be verified");
  });
  it("fails explicitly beyond 500 items instead of silently truncating", async () => {
    const f = fixture(); f.data.scopes = Array.from({ length: 501 }, (_, n) => ({ ...scope, id: n === 0 ? scope.id : id(100 + n) }));
    await expect(f.collect()).rejects.toThrow("exceeds 500 items");
  });
  it.each(["scope", "auditor"])("rejects missing %s references", async kind => {
    const f = fixture(); if (kind === "scope") f.data.criteria[0].scope_id = id(99); else f.data.agenda[0].auditor_team_member_id = id(99);
    await expect(f.collect()).rejects.toThrow("could not be verified");
  });
  it.each(["version", "company", "user"])("rejects a changed %s before returning a file", async kind => {
    const f = fixture((path, count) => {
      if (count < 2) return;
      if (kind === "version" && path.endsWith(selection.id)) return { ...audit, row_version: 8 };
      if (path === "/auth/me") return { ...identity, ...(kind === "company" ? { current_tenant_id: id(99) } : kind === "user" ? { id: id(99) } : {}) };
    });
    await expect(f.collect()).rejects.toThrow("context changed");
  });
  it("rejects access revoked at the final parent read", async () => {
    const f = fixture((path, count) => path.endsWith(selection.id) && count === 2 ? new Response(null, { status: 403 }) : undefined);
    await expect(f.collect()).rejects.toMatchObject({ status: 403 });
  });
  it("rejects stale selection before collecting its children", async () => {
    const f = fixture(path => path.endsWith(selection.id) ? { ...audit, row_version: 9 } : undefined);
    await expect(f.collect()).rejects.toBeInstanceOf(PlanExportError);
    expect(f.reader.mock.calls.some(([url]) => url.includes("?limit="))).toBe(false);
  });
  it("does not finish an aborted export", async () => {
    const controller = new AbortController();
    const f = fixture(path => { if (path.endsWith("/team-members")) controller.abort(); });
    await expect(f.collect(controller)).rejects.toMatchObject({ name: "AbortError" });
  });
});
