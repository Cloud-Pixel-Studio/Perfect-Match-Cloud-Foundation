import { findCompanyStoragePlan, formatStorageCapacity, parseStorageMb, storageTerms } from "./company-storage-plans";

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
  storagePlan?: string;
  estimatedStorageMb?: string | number;
};

type EnquiryErrors = Partial<Record<"company" | "seats" | "priority" | "isoInterests" | "storagePlan" | "estimatedStorageMb", string>>;

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

export function parseRequestedSeats(input: unknown): number | undefined {
  if (typeof input !== "string" && typeof input !== "number") return undefined;
  const value = String(input).trim();
  const seats = Number(value);
  return /^\d{1,5}$/.test(value) && seats >= 1 && seats <= 10_000 ? seats : undefined;
}

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
  const seats = parseRequestedSeats(input.seats);
  if (seats === undefined) {
    errors.seats = "Choose a whole number of seats from 1 to 10,000.";
  }
  const priority = productPriorities.find((option) => option.value === input.priority);
  if (!priority) errors.priority = "Choose one of the listed priorities.";
  const plan = findCompanyStoragePlan(input.storagePlan);
  if (input.storagePlan && !plan) errors.storagePlan = "Choose one of the listed plans.";
  const estimate = parseStorageMb(input.estimatedStorageMb);
  if (input.estimatedStorageMb !== undefined && input.estimatedStorageMb !== "" && estimate === undefined) {
    errors.estimatedStorageMb = "Enter a whole number of megabytes, starting at zero.";
  }
  if (
    input.isoInterests.length > isoInterestOptions.length ||
    input.isoInterests.some((value) => !isoInterestOptions.some((option) => option.value === value))
  ) {
    errors.isoInterests = "Choose only the listed ISO interests.";
  }
  if (Object.keys(errors).length > 0 || !priority || seats === undefined) return { ok: false, errors };

  const standards = isoInterestOptions.filter((option) => input.isoInterests.includes(option.value));
  const extraSeats = plan && plan.includedSeats !== null ? Math.max(0, seats - plan.includedSeats) : 0;
  const extraStorage = plan && estimate !== undefined ? Math.max(0, estimate - plan.capacityMb) : 0;
  const brief = [
    "Perfect Match QMS — demo brief",
    "",
    `Company: ${company || "Not specified"}`,
    "Company workspace: 1 independent workspace",
    `Team seats: ${seats}`,
    ...(estimate === undefined ? [] : [`Estimated retained storage: ${formatStorageCapacity(estimate)} per company.`]),
    `Main priority: ${priority.label}`,
    `ISO interests: ${standards.length ? standards.map((option) => `${option.label} (${option.state})`).join(", ") : "None selected"}`,
    "",
    "Requested product: Perfect Match QMS core, company workspace and team seats.",
    ...(plan ? [
      "",
      "Commercial scope to confirm",
      `Proposed plan: ${plan.name}`,
      `Proposed storage: ${formatStorageCapacity(plan.capacityMb)} per company, included in the recurring price.`,
      ...(extraSeats ? [`Additional seats to quote: ${extraSeats}.`] : []),
      ...(extraStorage ? [`Additional storage to quote: ${formatStorageCapacity(extraStorage)}.`] : []),
      storageTerms.counted,
      storageTerms.excluded,
      `Proposed alerts at ${storageTerms.alerts[0]}% and ${storageTerms.alerts[1]}%. ${storageTerms.full}`,
      `Proposed expansion blocks of ${formatStorageCapacity(storageTerms.expansionMb)}.`,
      storageTerms.expansion,
      "Final capacity, seats, ISO editions and price will be stated in the signed agreement.",
      "Ask for recurring charges and any one-time implementation costs separately.",
    ] : []),
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
