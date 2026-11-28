import { afterEach, expect, test, vi } from "vitest";
import { PUT } from "../app/api/identity/[...path]/route";
import { employeePhotoUploadLimit } from "./identity-path";

const id = "60000000-0000-4000-8000-000000000001";
const path = ["employees", id, id, "photo"];
const context = { params: Promise.resolve({ path }) };
const url = `http://localhost/api/identity/${path.join("/")}?expected_version=2`;

afterEach(() => vi.unstubAllGlobals());

test("portrait proxy rejects oversized uploads even without a content length", async () => {
  const upstream = vi.fn();
  vi.stubGlobal("fetch", upstream);
  const result = await PUT(new Request(url, {
    method: "PUT",
    body: new Uint8Array(employeePhotoUploadLimit + 1),
  }), context);
  expect(result.status).toBe(413);
  expect(upstream).not.toHaveBeenCalled();
});

test("portrait proxy preserves bytes and the selected record version", async () => {
  const upstream = vi.fn().mockResolvedValue(Response.json({}, { headers: { "X-Tenant-ID": id } }));
  vi.stubGlobal("fetch", upstream);
  const body = new Uint8Array([255, 216, 255, 217]);
  const result = await PUT(new Request(url, {
    method: "PUT", body, headers: { "Content-Type": "image/jpeg", "X-CSRF-Token": "test-token" },
  }), context);
  const [target, init] = upstream.mock.calls[0] as [URL, RequestInit];
  expect(target.searchParams.get("expected_version")).toBe("2");
  expect(init.body).toEqual(body);
  expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-token");
  expect(result.headers.get("X-Tenant-ID")).toBe(id);
});
