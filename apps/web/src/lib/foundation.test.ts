import { describe, expect, it } from "vitest";

import { foundationLabel } from "./foundation";

describe("foundationLabel", () => {
  it("maps runtime states to concise product labels", () => {
    expect(foundationLabel("ready")).toBe("Operational");
    expect(foundationLabel("checking")).toBe("Checking");
    expect(foundationLabel("unavailable")).toBe("Unavailable");
  });
});
