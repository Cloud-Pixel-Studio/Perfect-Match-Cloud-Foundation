import { describe, expect, it } from "vitest";

import { fetchActions } from "./action-center-data";

const queue = {
  scope: "mine", generated_at: "2026-11-17T12:00:00Z",
  summary: { total: 1, overdue: 0, due_soon: 0, unassigned: 1, by_source: { capa: 1 } },
  items: [{ id: "capa:10000000-0000-4000-8000-000000000001", source: "capa", source_id: "10000000-0000-4000-8000-000000000001", unit_id: null, title: "Synthetic inspection follow-up", context: "DEMO", state: "open", urgency: "normal", due_date: null, overdue: false, assigned_to_user_id: null, assignee_name: null, target_workspace: "capa", target_record_id: "10000000-0000-4000-8000-000000000001", target_subrecord_id: null, target_process_id: null, updated_at: "2026-11-17T12:00:00Z" }],
};

const respond = (body: unknown, status = 200): typeof fetch => async () => Response.json(body, { status });

describe("action queue reads", () => {
  it("returns authorized data using the same-origin authenticated API", async () => {
    const calls: { url: string; options?: RequestInit }[] = [];
    const request: typeof fetch = async (url, options) => { calls.push({ url: String(url), options }); return Response.json(queue); };
    expect(await fetchActions("mine", 5, request)).toEqual({ ok: true, data: queue });
    expect(calls).toEqual([{ url: "/api/identity/action-center?scope=mine&limit=5", options: { credentials: "include", cache: "no-store" } }]);
  });

  it.each([[401, "expired"], [403, "denied"], [500, "unavailable"], [404, "unavailable"]] as const)("classifies HTTP %s without exposing a response body", async (status, reason) => {
    expect(await fetchActions("mine", 100, respond({ detail: "sensitive server diagnostic" }, status))).toEqual({ ok: false, reason });
  });

  it("treats a network failure as unavailable", async () => {
    expect(await fetchActions("mine", 100, async () => { throw new Error("private upstream URL"); })).toEqual({ ok: false, reason: "unavailable" });
  });

  it("rejects malformed JSON", async () => {
    expect(await fetchActions("mine", 100, async () => new Response("invalid"))).toEqual({ ok: false, reason: "unavailable" });
  });

  it("rejects a response for another requested scope", async () => {
    expect(await fetchActions("team", 100, respond(queue))).toEqual({ ok: false, reason: "unavailable" });
  });

  it.each([
    null,
    { ...queue, items: {} },
    { ...queue, summary: { ...queue.summary, total: -1 } },
    { ...queue, generated_at: "not a date" },
    { ...queue, items: [{ ...queue.items[0], title: null }] },
    { ...queue, items: [{ ...queue.items[0], target_workspace: "permissions" }] },
    { ...queue, items: [{ ...queue.items[0], target_workspace: ["capa"] }] },
    { ...queue, items: [{ ...queue.items[0], source: ["capa"] }] },
    { ...queue, items: [{ ...queue.items[0], urgency: ["normal"] }] },
    { ...queue, items: [{ ...queue.items[0], due_date: "invalid" }] },
  ])("rejects an invalid display contract: %j", async (body) => {
    expect(await fetchActions("mine", 100, respond(body))).toEqual({ ok: false, reason: "unavailable" });
  });
});
