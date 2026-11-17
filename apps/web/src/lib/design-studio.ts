export const designAssetKinds = [
  "hero_banner",
  "product_overview",
  "dashboard_mockup",
  "social_post",
  "audit_promo",
  "capability_infographic",
] as const;

export type DesignAssetKind = (typeof designAssetKinds)[number];
export type DesignJobState =
  | "draft"
  | "validated"
  | "generating"
  | "quality_review"
  | "approved"
  | "rejected"
  | "cancelled";
export type DataClassification = "public" | "internal" | "confidential" | "restricted";

export type DesignAssetSpec = {
  slug: string;
  kind: DesignAssetKind;
  title: string;
  purpose: string;
  width: number;
  height: number;
  source: "generated-background" | "real-synthetic-screenshot" | "deterministic-layout";
  disclosure: string;
};

export type DesignBrief = {
  tenantId: string;
  requestedByUserId: string;
  kind: DesignAssetKind;
  objective: string;
  audience: string;
  exactCopy: string[];
  dataClassification: DataClassification;
  containsCustomerData: boolean;
  providerAllowsExternalProcessing: boolean;
};

export const designAssetCatalog: readonly DesignAssetSpec[] = [
  {
    slug: "platform-hero",
    kind: "hero_banner",
    title: "Banner principal",
    purpose: "Presentación general de la plataforma",
    width: 1600,
    height: 900,
    source: "generated-background",
    disclosure: "Ilustración de marca; no representa una certificación.",
  },
  {
    slug: "saas-product-overview",
    kind: "product_overview",
    title: "Presentación del producto SaaS",
    purpose: "Explicar tenant privado, responsabilidades y evidencia",
    width: 1600,
    height: 900,
    source: "real-synthetic-screenshot",
    disclosure: "Captura real del entorno de demostración con datos sintéticos.",
  },
  {
    slug: "dashboard-mockup",
    kind: "dashboard_mockup",
    title: "Mockup del dashboard",
    purpose: "Mostrar la interfaz real sin inventar pantallas",
    width: 1600,
    height: 1000,
    source: "real-synthetic-screenshot",
    disclosure: "Captura real del entorno de demostración con datos sintéticos.",
  },
  {
    slug: "quality-linkedin",
    kind: "social_post",
    title: "Publicación LinkedIn",
    purpose: "Comunicar gestión de calidad basada en evidencia",
    width: 1200,
    height: 1200,
    source: "generated-background",
    disclosure: "Visual conceptual sin métricas, clientes ni certificaciones.",
  },
  {
    slug: "audit-readiness",
    kind: "audit_promo",
    title: "Auditorías y cumplimiento",
    purpose: "Promover preparación y trazabilidad sin afirmar certificación",
    width: 1200,
    height: 628,
    source: "deterministic-layout",
    disclosure: "Objetivo de producto; no constituye certificación ISO.",
  },
  {
    slug: "qms-capabilities",
    kind: "capability_infographic",
    title: "Capacidades principales",
    purpose: "Resumir el QMS documentado",
    width: 1200,
    height: 1200,
    source: "deterministic-layout",
    disclosure: "Resume funciones implementadas o claramente identificadas como planificadas.",
  },
] as const;

const allowedTransitions: Record<DesignJobState, readonly DesignJobState[]> = {
  draft: ["validated", "cancelled"],
  validated: ["generating", "cancelled"],
  generating: ["quality_review", "cancelled"],
  quality_review: ["approved", "rejected"],
  approved: [],
  rejected: ["draft", "cancelled"],
  cancelled: [],
};

export function validateDesignBrief(brief: DesignBrief): string[] {
  const errors: string[] = [];
  if (!brief.tenantId.trim() || !brief.requestedByUserId.trim()) {
    errors.push("Tenant and requesting user are required.");
  }
  if (brief.objective.trim().length < 12 || brief.objective.length > 500) {
    errors.push("Objective must contain between 12 and 500 characters.");
  }
  if (brief.audience.trim().length < 3 || brief.audience.length > 160) {
    errors.push("Audience must contain between 3 and 160 characters.");
  }
  if (brief.exactCopy.some((line) => !line.trim() || line.length > 240)) {
    errors.push("Exact copy lines must be non-empty and no longer than 240 characters.");
  }
  if (
    brief.containsCustomerData ||
    brief.dataClassification === "confidential" ||
    brief.dataClassification === "restricted"
  ) {
    errors.push("Customer, confidential or restricted data cannot be sent to a generation provider.");
  }
  if (!brief.providerAllowsExternalProcessing) {
    errors.push("The selected provider is not approved for external processing.");
  }
  return errors;
}

export function canTransitionDesignJob(from: DesignJobState, to: DesignJobState): boolean {
  return allowedTransitions[from].includes(to);
}

export function requiresHumanApproval(state: DesignJobState): boolean {
  return state === "quality_review";
}

