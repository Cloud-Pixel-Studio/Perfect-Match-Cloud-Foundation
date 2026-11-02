import { NextRequest } from "next/server";
import { afterEach, expect, test, vi } from "vitest";

import { proxy } from "./proxy";

afterEach(() => vi.unstubAllEnvs());

test("production CSP uses a fresh nonce and replaces client-supplied policy", () => {
  vi.stubEnv("NODE_ENV", "production");
  const request = new NextRequest("http://localhost/", {
    headers: { "x-nonce": "attacker", "Content-Security-Policy": "script-src *" },
  });
  const first = proxy(request);
  const second = proxy(request);
  const policy = first.headers.get("Content-Security-Policy")!;
  expect(policy).toContain("'strict-dynamic'");
  expect(policy).not.toContain("unsafe-inline");
  expect(policy).not.toContain("unsafe-eval");
  expect(policy).not.toContain("attacker");
  expect(policy).not.toEqual(second.headers.get("Content-Security-Policy"));
  const nonce = first.headers.get("x-middleware-request-x-nonce");
  expect(nonce).toMatch(/^[A-Za-z0-9+/]{22}==$/);
  expect(policy).toContain(`'nonce-${nonce}'`);
  expect(first.headers.get("Cache-Control")).toBe("private, no-store");
});
