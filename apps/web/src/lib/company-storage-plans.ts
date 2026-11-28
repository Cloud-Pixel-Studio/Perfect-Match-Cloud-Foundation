export const companyStoragePlans = [
  {
    id: "basic", name: "Basic", capacityMb: 5_000,
    use: "Start your quality system and organize your document archive.",
    scope: "1 company, 3 seats and 1 ISO addon, subject to availability.",
  },
  {
    id: "team", name: "Team", capacityMb: 25_000,
    use: "Share documents and evidence across departments.",
    scope: "Seats and ISO editions agreed in your contract.",
  },
  {
    id: "professional", name: "Professional", capacityMb: 100_000,
    use: "Manage more sites, revisions and audits.",
    scope: "Seats and ISO editions agreed in your contract.",
  },
  {
    id: "enterprise", name: "Enterprise", capacityMb: 250_000,
    use: "Support high volumes of retained evidence.",
    scope: "Custom capacity by agreement.",
  },
] as const;

export type CompanyStoragePlan = (typeof companyStoragePlans)[number];
export type CompanyStoragePlanId = CompanyStoragePlan["id"];

export function findCompanyStoragePlan(id: unknown): CompanyStoragePlan | undefined {
  return companyStoragePlans.find(plan => plan.id === id);
}

export function formatStorageCapacity(capacityMb: number): string {
  return `${capacityMb.toLocaleString("en-US")} MB`;
}

export const storageTerms = {
  counted: "Documents and retained revisions, employee photos, evidence, and attachments use the company’s allowance.",
  excluded: "Managed backups, internal previews, and temporary files are outside the company’s allowance.",
  full: "At the limit, new uploads pause. Authorized users can still view, download and export existing records.",
  expansion: "Extra capacity requires customer approval. No automatic overage charges.",
  expansionMb: 25_000,
  alerts: [80, 90],
} as const;
