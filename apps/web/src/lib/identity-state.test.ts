import { describe, expect, it } from "vitest";

import { unauthenticatedState } from "./identity-state";

describe("identity response state", () => {
  it("distinguishes anonymous and expired sessions without exposing session data", () => {
    expect(unauthenticatedState(401, false)).toBe("anonymous");
    expect(unauthenticatedState(401, true)).toBe("expired");
  });

  it("maps authorization and service failures to dedicated states", () => {
    expect(unauthenticatedState(403, false)).toBe("denied");
    expect(unauthenticatedState(503, false)).toBe("error");
  });
});
