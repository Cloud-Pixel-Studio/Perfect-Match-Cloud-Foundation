import { describe, expect, it } from "vitest";

import {
  canTransitionDesignJob,
  designAssetCatalog,
  requiresHumanApproval,
  validateDesignBrief,
  type DesignBrief,
} from "./design-studio";

const safeBrief: DesignBrief = {
  tenantId: "tenant-demo",
  requestedByUserId: "user-demo",
  kind: "social_post",
  objective: "Explain evidence-based quality work without certification claims.",
  audience: "Quality leaders",
  exactCopy: ["Work with clarity.", "Improve with evidence."],
  dataClassification: "public",
  containsCustomerData: false,
  providerAllowsExternalProcessing: true,
};

describe("design studio safety contract", () => {
  it("keeps every requested demonstration asset explicit and exportable", () => {
    expect(designAssetCatalog).toHaveLength(6);
    expect(new Set(designAssetCatalog.map(({ slug }) => slug)).size).toBe(6);
    expect(designAssetCatalog.every(({ width, height }) => width >= 1200 && height >= 628)).toBe(true);
  });

  it("accepts a public synthetic brief", () => {
    expect(validateDesignBrief(safeBrief)).toEqual([]);
  });

  it.each(["confidential", "restricted"] as const)(
    "blocks %s data from external generation",
    (dataClassification) => {
      expect(validateDesignBrief({ ...safeBrief, dataClassification })).toContain(
        "Customer, confidential or restricted data cannot be sent to a generation provider.",
      );
    },
  );

  it("blocks customer data even when it is mislabeled public", () => {
    expect(validateDesignBrief({ ...safeBrief, containsCustomerData: true })).toContain(
      "Customer, confidential or restricted data cannot be sent to a generation provider.",
    );
  });

  it("requires controlled state transitions and human approval", () => {
    expect(canTransitionDesignJob("draft", "validated")).toBe(true);
    expect(canTransitionDesignJob("draft", "approved")).toBe(false);
    expect(canTransitionDesignJob("quality_review", "approved")).toBe(true);
    expect(requiresHumanApproval("quality_review")).toBe(true);
    expect(requiresHumanApproval("generating")).toBe(false);
  });
});
