import { expect, test } from "vitest";

import { isAllowedIdentityPath } from "./identity-path";

test("resource UUIDs are accepted for organization and workflow routes", () => {
  const id = "60000000-0000-4000-8000-000000000001";
  expect(isAllowedIdentityPath(["organization", "units", id])).toBe(true);
  expect(isAllowedIdentityPath(["workflows", id, "versions"])).toBe(true);
  expect(isAllowedIdentityPath(["workflow-instances", id, "transitions"])).toBe(true);
  expect(isAllowedIdentityPath(["documents", id, "revisions", id, "file"])).toBe(true);
  expect(isAllowedIdentityPath(["controls", id, "activate"])).toBe(true);
  expect(isAllowedIdentityPath(["controls", id, "activities"])).toBe(true);
  expect(isAllowedIdentityPath(["controls", id, "evidence-requirements"])).toBe(true);
  expect(isAllowedIdentityPath(["control-activities", id])).toBe(true);
  expect(isAllowedIdentityPath(["control-evidence-requirements", id])).toBe(true);
  expect(isAllowedIdentityPath(["control-instances", id, "transition"])).toBe(true);
  expect(isAllowedIdentityPath(["risks", id, "transition"])).toBe(true);
  expect(isAllowedIdentityPath(["nonconformities", id, "transition"])).toBe(true);
  expect(isAllowedIdentityPath(["capas", id])).toBe(true);
});

test("proxy refuses unknown roots, path traversal, embedded URLs and invalid IDs", () => {
  for (const path of [[], ["admin"], ["auth", ".."], ["auth", "%2e%2e"],
    ["auth", "https://example.test"], ["auth", "a/b"], ["organization", "units", "1234"],
    ["auth", ...Array<string>(16).fill("me")]]) {
    expect(isAllowedIdentityPath(path)).toBe(false);
  }
});
