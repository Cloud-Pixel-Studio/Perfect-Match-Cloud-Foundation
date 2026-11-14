import { expect, test } from "vitest";
import { emptyHistoryFilters, matchesGrantCommand, parseQMSGrantPage, qmsHistoryQuery } from "./qms-access-history";
const tenant = "a1000000-0000-4000-8000-000000000001";
const viewer = { tenantId: tenant, userId: "a2000000-0000-4000-8000-000000000001", role: "member" };
const row = { id: "a4000000-0000-4000-8000-000000000001", user_id: viewer.userId,
  unit_id: "a3000000-0000-4000-8000-000000000001", capability: "documents.read", status: "active",
  granted_by_user_id: "a2000000-0000-4000-8000-000000000002", created_at: "2026-11-14T12:00:00Z",
  revoked_at: null, revoked_by_user_id: null, member_name: null, unit_name: "Quality", unit_code: "QA", unit_status: "active" };
const page = { tenant_id: tenant, viewer_user_id: viewer.userId, viewer_role: viewer.role, items: [row], next_cursor: null };

test("history rejects identity, company, role and other-member response confusion", () => {
  expect(parseQMSGrantPage(page, viewer)).not.toBeNull();
  for (const change of [{ tenant_id: row.unit_id }, { viewer_user_id: row.granted_by_user_id }, { viewer_role: "owner" },
    { items: [{ ...row, user_id: row.granted_by_user_id }] }]) expect(parseQMSGrantPage({ ...page, ...change }, viewer)).toBeNull();
});
test("history refuses duplicated rows, unbounded cursors and inconsistent revocation", () => {
  for (const change of [{ items: [row, row] }, { next_cursor: "next" }, { next_cursor: "x".repeat(2049) },
    { items: [{ ...row, status: "revoked" }] }, { items: [{ ...row, created_at: "123" }] }]) {
    expect(parseQMSGrantPage({ ...page, ...change }, viewer)).toBeNull();
  }
});
test("revocation preserves the original issuer while requiring the current reviewer", () => {
  const revoked = { ...row, status: "revoked", revoked_by_user_id: viewer.userId, revoked_at: "2026-11-14T13:00:00Z" };
  expect(matchesGrantCommand(revoked, viewer.userId, row, "revoke")).toBe(true);
  expect(matchesGrantCommand({ ...revoked, granted_by_user_id: viewer.userId }, viewer.userId, row, "revoke")).toBe(false);
  expect(matchesGrantCommand({ ...revoked, revoked_by_user_id: row.granted_by_user_id }, viewer.userId, row, "revoke")).toBe(false);
});
test("search and cursor remain URL query data", () => {
  const query = qmsHistoryQuery({ ...emptyHistoryFilters, q: "  QA & 100%_  " }, "opaque+/=");
  const url = new URL(query, "https://example.invalid");
  expect(url.searchParams.get("q")).toBe("QA & 100%_");
  expect(url.searchParams.get("cursor")).toBe("opaque+/=");
  expect(url.searchParams.get("limit")).toBe("20");
});
