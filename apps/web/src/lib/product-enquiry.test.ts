import { describe, expect, it } from "vitest";

import {
  buildProductEnquiry,
  DEMO_CONTACT_EMAIL,
  DEMO_ENQUIRY_SUBJECT,
  type ProductEnquiryInput,
} from "./product-enquiry";

const enquiry: ProductEnquiryInput = {
  company: "",
  seats: "25",
  priority: "general-qms",
  isoInterests: [],
};

describe("product demo enquiry", () => {
  it("prepares a brief without personal details and keeps the approved recipient fixed", () => {
    const result = buildProductEnquiry(enquiry);
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected valid enquiry");
    const url = new URL(result.mailto);
    expect(url.protocol).toBe("mailto:");
    expect(url.pathname).toBe("Demo@invperfectmatch.com");
    expect(DEMO_CONTACT_EMAIL).toBe("Demo@invperfectmatch.com");
    expect(url.searchParams.get("subject")).toBe(DEMO_ENQUIRY_SUBJECT);
    expect(url.searchParams.get("body")).toBe(result.brief);
    expect(result.brief).toContain("Company workspace: 1 independent workspace");
    expect(result.brief).toContain("Company: Not specified");
  });

  it.each(["", "0", "-1", "1.5", "1e3", "10001", "Infinity", "abc", Number.NaN])(
    "rejects an invalid seat quantity: %s",
    (seats) => {
      const result = buildProductEnquiry({ ...enquiry, seats });
      expect(result.ok).toBe(false);
      if (result.ok) throw new Error("Expected rejected enquiry");
      expect(result.errors.seats).toBeTruthy();
      expect(result).not.toHaveProperty("mailto");
      expect(result).not.toHaveProperty("brief");
    },
  );

  it.each([1, 10_000])("accepts the supported seat boundary: %s", (seats) => {
    const result = buildProductEnquiry({ ...enquiry, seats });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.seats).toBe(seats);
  });

  it("keeps company text and line breaks inside the encoded body, never in recipient headers", () => {
    const result = buildProductEnquiry({
      ...enquiry,
      company: "Acme\r\nBcc: other@example.test &cc=third@example.test?subject=override",
    });
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected safe encoded enquiry");
    expect(result.company).not.toMatch(/[\r\n]/);
    const url = new URL(result.mailto);
    expect(url.pathname).toBe(DEMO_CONTACT_EMAIL);
    expect([...url.searchParams.keys()]).toEqual(["subject", "body"]);
    expect(url.searchParams.get("subject")).toBe(DEMO_ENQUIRY_SUBJECT);
    expect(url.searchParams.get("body")).toContain(result.company);
  });

  it("bounds company text and rejects an unsupported priority or ISO value", () => {
    expect(buildProductEnquiry({ ...enquiry, company: "x".repeat(121) }).ok).toBe(false);
    expect(buildProductEnquiry({ ...enquiry, priority: "<script>" }).ok).toBe(false);
    expect(buildProductEnquiry({ ...enquiry, isoInterests: ["27001"] }).ok).toBe(false);
    expect(buildProductEnquiry({ ...enquiry, isoInterests: ["9001", "14001", "45001", "9001"] }).ok).toBe(false);
  });

  it("produces a bounded Unicode payload and retains the actual addon availability labels", () => {
    const result = buildProductEnquiry({
      ...enquiry,
      company: "漢".repeat(120),
      seats: 10_000,
      isoInterests: ["45001", "9001", "14001"],
    });
    expect(result.ok).toBe(true);
    if (!result.ok) throw new Error("Expected bounded enquiry");
    expect(result.brief.length).toBeLessThan(1000);
    expect(result.mailto.length).toBeLessThan(3000);
    expect(result.isoInterests).toEqual(["9001", "14001", "45001"]);
    expect(result.brief).toContain("ISO 9001 (In preparation)");
    expect(result.brief).toContain("ISO 14001 (Planned)");
    expect(result.brief).toContain("ISO 45001 (Planned)");
    expect(result.brief).toContain("not a quote, order or subscription");
  });

  it("handles malformed Unicode without breaking URI generation", () => {
    const result = buildProductEnquiry({ ...enquiry, company: "Acme\ud800" });
    expect(result.ok).toBe(true);
    if (result.ok) expect(new URL(result.mailto).searchParams.get("body")).toBe(result.brief);
  });
});
