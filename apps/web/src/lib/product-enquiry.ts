export const DEMO_CONTACT_EMAIL = "Demo@invperfectmatch.com";
export const DEMO_ENQUIRY_SUBJECT = "Perfect Match QMS demo request";

export const productPriorities = [
  { value: "documents", label: "Documents" },
  { value: "risks", label: "Risks" },
  { value: "corrective-actions", label: "Corrective actions" },
  { value: "general-qms", label: "General QMS" },
] as const;

export const isoInterestOptions = [
  { value: "9001", label: "ISO 9001", state: "In preparation" },
  { value: "14001", label: "ISO 14001", state: "Planned" },
  { value: "45001", label: "ISO 45001", state: "Planned" },
] as const;

export type ProductPriority = (typeof productPriorities)[number]["value"];
export type ISOInterest = (typeof isoInterestOptions)[number]["value"];

export type ProductEnquiryInput = {
  company: string;
  seats: number | string;
  priority: string;
  isoInterests: readonly string[];
};

type EnquiryErrors = Partial<Record<"company" | "seats" | "priority" | "isoInterests", string>>;

export type ProductEnquiryResult =
  | { ok: false; errors: EnquiryErrors }
  | {
      ok: true;
      company: string;
      seats: number;
      priority: ProductPriority;
      isoInterests: ISOInterest[];
      brief: string;
      mailto: string;
    };

export function buildProductEnquiry(input: ProductEnquiryInput): ProductEnquiryResult {
  const errors: EnquiryErrors = {};
  if (input.company.length > 120) {
    errors.company = "Use no more than 120 characters for the company name.";
  }
  const company = input.company
    .toWellFormed()
    .replace(/[\p{Cc}\p{Cf}]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
  const seatText = String(input.seats).trim();
  const seats = Number(seatText);
  if (!/^\d{1,5}$/.test(seatText) || !Number.isInteger(seats) || seats < 1 || seats > 10_000) {
    errors.seats = "Choose a whole number of seats from 1 to 10,000.";
  }
  const priority = productPriorities.find((option) => option.value === input.priority);
  if (!priority) errors.priority = "Choose one of the listed priorities.";
  if (
    input.isoInterests.length > isoInterestOptions.length ||
    input.isoInterests.some((value) => !isoInterestOptions.some((option) => option.value === value))
  ) {
    errors.isoInterests = "Choose only the listed ISO interests.";
  }
  if (Object.keys(errors).length > 0 || !priority) return { ok: false, errors };

  const standards = isoInterestOptions.filter((option) => input.isoInterests.includes(option.value));
  const brief = [
    "Perfect Match QMS — demo brief",
    "",
    `Company: ${company || "Not specified"}`,
    "Company workspace: 1 independent workspace",
    `Team seats: ${seats}`,
    `Main priority: ${priority.label}`,
    `ISO interests: ${standards.length ? standards.map((option) => `${option.label} (${option.state})`).join(", ") : "None selected"}`,
    "",
    "Requested product: Perfect Match QMS base, company workspace and team seats.",
    "ISO selections express interest only; availability must be confirmed.",
    "This brief is not a quote, order or subscription.",
  ].join("\n");

  return {
    ok: true,
    company,
    seats,
    priority: priority.value,
    isoInterests: standards.map((option) => option.value),
    brief,
    mailto: `mailto:${DEMO_CONTACT_EMAIL}?subject=${encodeURIComponent(DEMO_ENQUIRY_SUBJECT)}&body=${encodeURIComponent(brief)}`,
  };
}
