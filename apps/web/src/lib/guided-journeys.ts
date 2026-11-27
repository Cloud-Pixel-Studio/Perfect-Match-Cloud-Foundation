import type { WorkspaceId } from "./workspace-navigation";
import type { GuideRecord, GuideResource, GuideSnapshot } from "./guided-journey-data";

export type GuideStep = {
  id: string; title: string; why: string; instructions: string[];
  expected: string; doneWhen: string; resource?: GuideResource;
  workspace?: WorkspaceId; productGap?: string; limitation?: string;
};
export type GuideJourney = {
  id: "initial" | "improve" | "transition" | "migrate" | "audit" | "expand";
  title: string; summary: string; outcome: string; steps: GuideStep[];
};

const processes: GuideStep = {
  id: "process-map", title: "Map processes and responsibilities",
  why: "Your work needs an explicit operational scope and accountable owners.",
  instructions: ["Select the organizational unit this guide will inspect; identify its processes and responsible people.", "Open Processes to describe inputs, outputs and interfaces. Review the active records before adding a duplicate."],
  expected: "A process map with owners and clear inputs and outputs.",
  doneWhen: "The responsible people have reviewed the relevant processes and their boundaries for this project.",
  resource: "processes", workspace: "processes",
  limitation: "Active processes are visible unit records, not an approved project scope or baseline.",
};
const documents: GuideStep = {
  id: "document-control", title: "Prepare controlled information",
  why: "People need identifiable instructions and records with a controlled revision.",
  instructions: ["Inspect existing document codes and revisions before preparing the information the process needs.", "Upload the required PDF, submit it for independent review, and release the approved revision using Document control."],
  expected: "Identified documents with current released revisions and a review history.",
  doneWhen: "Relevant content has been reviewed for the project, the correct revision is available and obsolete copies are addressed.",
  resource: "documents", workspace: "documents",
  limitation: "An active document record does not establish its applicability or technical adequacy for an ISO requirement.",
};
const implementations: GuideStep = {
  id: "control-implementation", title: "Implement controls and supply evidence",
  why: "A written procedure needs completed work and evidence that another authorized person can review.",
  instructions: ["Choose the control applicable to the process and inspect its assigned activities and evidence requirements.", "Complete mandatory activities, supply the required evidence and obtain independent acceptance before recording the implementation as implemented."],
  expected: "Control implementations with traceable activities, documentary evidence and review decisions.",
  doneWhen: "Applicable mandatory activities are complete and required evidence is accepted through the control workflow.",
  resource: "implementations", workspace: "controls",
  limitation: "Submitted or under-review work is not accepted evidence. A record with no configured requirements is not proof of conformity.",
};
const risks: GuideStep = {
  id: "risk-response", title: "Evaluate risks and plan responses",
  why: "Decisions should reflect the consequences of gaps and changes in the selected scope.",
  instructions: ["Review risks and opportunities, their causes, potential effects, owners and current evaluations.", "Connect the relevant controls and documents; record treatment, dates and follow-up decisions instead of assuming a lower score proves effectiveness."],
  expected: "An assessed risk register with accountable responses and traceable support.",
  doneWhen: "Responsible people have reviewed the project's risks, responses and residual uncertainty and recorded follow-up decisions.",
  resource: "risks", workspace: "risks",
};
const capas: GuideStep = {
  id: "corrective-follow-up", title: "Resolve issues and verify corrective actions",
  why: "An action marked done still needs verification and an effectiveness decision where required.",
  instructions: ["Inspect the CAPA source, root-cause analysis, actions, dates and linked evidence.", "Complete the work, obtain verification by another authorized person and record the effectiveness review before closing the case."],
  expected: "Corrective actions with implementation, independent verification and effectiveness history.",
  doneWhen: "Relevant actions have been independently verified and the authorized effectiveness and closure decisions are recorded.",
  resource: "capas", workspace: "capa",
  limitation: "A closed CAPA does not automatically close its source nonconformity or certify an entire QMS.",
};
const audits: GuideStep = {
  id: "audit-plan", title: "Prepare the audit plan and participants",
  why: "The evaluation needs a defined scope, criteria, team and realistic schedule.",
  instructions: ["Open Internal audits to review the program, structured scope, criteria and planned dates.", "Plan the team and agenda, assess independence and competence with appropriate support, and inspect the printable plan."],
  expected: "An audit plan with scope, criteria, team, agenda and recorded preparation reviews.",
  doneWhen: "Authorized reviewers have assessed the actual plan and its support; execution is separately authorized when that workflow becomes available.",
  resource: "audits", workspace: "internal-audits",
  limitation: "This workspace supports planning. A planned audit is not ready for execution, an issued report or certification.",
};
const pending = (id: string, title: string, why: string, instructions: string[], expected: string, doneWhen: string, productGap: string): GuideStep => ({ id, title, why, instructions, expected, doneWhen, productGap });
const normative = pending("normative-profile", "Confirm the standard, edition and applicability",
  "Implementation guidance must refer to an identified, reviewed edition and the company's actual scope.",
  ["Identify the intended standard and edition with the responsible quality professional.",
    "Open the context register and choose QMS scope. Define the boundaries, products and services, and applicability, then have an independent reviewer approve the scope.",
    "Record which existing processes and controls would support each applicable requirement."],
  "A reviewed versioned profile and an applicability matrix for the project.",
  "The authorized profile has been released and the project's applicability decisions are reviewed.",
  "Versioned ISO profiles, requirement mappings and project applicability are not implemented. This guide cannot approve an ISO profile.");
const management = pending("management-review", "Review performance and management decisions",
  "Preparation includes performance, resources and leadership decisions, not only a collection of documents.",
  ["Identify the objectives, measurements, training needs and management review inputs relevant to this project.", "Review unresolved gaps and decisions with the accountable leadership before accepting a readiness conclusion."],
  "Traceable performance information, competence support and management review decisions.",
  "The required inputs have been evaluated and leadership has recorded decisions and follow-up responsibilities.",
  "The integrated objectives, KPI, training and management review workflows are not implemented. Do not mark this stage complete from unrelated records.");
const execution = pending("execute-audit", "Execute the audit and follow up findings",
  "Planning and readiness diagnostics must remain separate from an executed audit and its conclusions.",
  ["Identify the evidence and findings workflow needed for the planned evaluation.", "When execution is available, record findings, follow-up actions and an independently reviewed report through its authorized workflow."],
  "An executed audit with reviewed evidence, findings, follow-up and controlled conclusions.",
  "The authorized execution, report and closure decisions are recorded with their supporting evidence.",
  "Audit ready/start, execution, findings, issued reports and closure are not implemented. No execution command is available here.");

export const journeys: GuideJourney[] = [
  { id: "initial", title: "Build a QMS from the beginning", summary: "Establish the working structure, controlled information and evidence for a new quality system.", outcome: "A reviewed implementation baseline and a documented preparation decision; not automatic ISO certification.", steps: [
    processes, normative, documents, implementations, risks,
    pending("people-and-performance", "Prepare people, objectives and measurements", "The system needs competent people, resources and evidence of its performance.", ["Identify who performs and reviews each activity and the support they need.", "Define measurable objectives and how their results will be reviewed; list missing training or measurement capability."], "Defined objectives, competence needs, resources and measurement responsibilities.", "Competence and performance information have been reviewed with evidence and accountable owners.", "Integrated training, objectives and KPI workflows are not implemented; their completion cannot be verified here."),
    audits, management,
  ] },
  { id: "improve", title: "Improve an existing quality system", summary: "Understand the current system, preserve working records and address the changes that matter.", outcome: "A controlled improvement with reviewed impact, supporting records and an accepted new baseline.", steps: [
    { ...processes, id: "existing-baseline", title: "Inspect the existing process baseline", instructions: ["Review the active process map and the people accountable for its interfaces.", "Identify what should be retained and which issues justify a change; avoid replacing valid records only to restart the system."] },
    pending("change-impact", "Assess and authorize the proposed change", "A change can affect other processes, documents, competence and existing commitments.", ["Describe the reason, affected scope, risks and acceptance criteria for the proposed change.", "Identify every dependent record and obtain the required authorization before implementing the change."], "An approved change with an impact assessment and an agreed implementation plan.", "Authorized people have approved the scope, impact, ownership, resources and verification criteria.", "A cross-module change dossier and project-wide approved baseline are not implemented."),
    documents, implementations, risks, capas,
    pending("accept-change", "Verify the change and accept the revised baseline", "Completing an edit is different from demonstrating that the change achieved its intended result.", ["Review the revised information and the results of the implemented actions.", "Check unintended effects and obtain a documented acceptance decision with unresolved items clearly assigned."], "A reviewed change outcome and a traceable accepted baseline.", "The change owner and reviewer have evaluated results and recorded the acceptance decision.", "Global change verification and baseline acceptance are not implemented. Individual record histories remain available."),
  ] },
  { id: "transition", title: "Transition to another ISO edition", summary: "Preserve the previous edition's history while planning and verifying the required changes.", outcome: "An authorized transition based on reviewed differences, evidence and a preserved previous baseline.", steps: [
    pending("source-baseline", "Identify the source edition and its baseline", "Historical decisions and evidence must retain the edition against which they were evaluated.", ["Inventory the current edition, scope, assessments and records that support the existing system.", "Preserve the historical baseline and identify source information that has not yet been verified."], "An identified source edition with a preserved baseline and provenance.", "The source scope, edition and supporting history have been reviewed and recorded.", "Source/target edition baselines and formal transition projects are not implemented."),
    normative,
    pending("edition-comparison", "Evaluate differences and assign gap actions", "A revision label is not a comparison of requirements between editions.", ["Compare the reviewed source and target profiles without rewriting historical assessments.", "Record each gap, its impact, responsible person, target date and the evidence needed to close it."], "A versioned difference matrix and an owned transition action plan.", "Each relevant difference has an applicability decision and a reviewed action or supported no-change rationale.", "Edition comparison, normative gap assessment and transition-action workflows are not implemented."),
    implementations, documents, risks, audits,
    pending("transition-decision", "Review and authorize the transition outcome", "The final decision needs the actual results and residual gaps, not a count of uploaded files.", ["Review the actions and evidence against the released target profile.", "Record unresolved risk, the transition decision and how prior-edition records remain accessible."], "A reviewed transition decision with preserved historical references.", "Authorized reviewers have accepted the target baseline and recorded every remaining condition.", "Formal transition decisions and controlled edition migration are not implemented."),
  ] },
  { id: "migrate", title: "Move from another QMS or files", summary: "Prepare a controlled move of data, files and relationships with explicit checks and provenance.", outcome: "Reconciled, reviewed information in the target QMS with source history and recovery evidence preserved.", steps: [
    pending("source-inventory", "Inventory the source information and files", "The migration scope determines what can be validated and what must remain as historical reference.", ["List record types, files, relationships, source identifiers and owners in the current system.", "Classify duplicates, incomplete records, restrictions and information that must not be imported as an approval."], "An owned source inventory with quality and retention decisions.", "The customer has agreed the inventory, mappings, exclusions and historical treatment.", "Customer migration inventories, external identifiers and mapping workspaces are not implemented."),
    processes,
    pending("trial-import", "Validate mappings and rehearse the import", "A rehearsal must detect relationship and file problems before a controlled migration.", ["Prepare mappings and recoverable backups, then validate a copy in an isolated environment.", "Compare record counts, relationships and file hashes and resolve errors before requesting import authorization."], "A reviewed rehearsal report, recovery procedure and accepted mappings.", "The isolated rehearsal and restoration have been validated and the import is explicitly authorized.", "Commercial batch validation, preview, trial import and migration authorization are not implemented. Demo seed scripts are not a customer importer."),
    { ...documents, id: "manual-document-entry", title: "Review document handling in the target QMS", instructions: ["Inspect how individual documents and PDF revisions are created and reviewed in the target scope.", "Keep original approvals and authorship as identified historical support; do not recreate them as actions performed by a current SaaS user."], limitation: "Individual document upload is available. Existing target records do not prove that a source migration or its history was validated." },
    implementations,
    pending("reconcile-migration", "Reconcile information and accept the migration", "A technically completed load can still lose relationships, versions or historical context.", ["Reconcile the agreed inventory against imported records and files, including errors and exceptions.", "Review provenance and access, obtain customer acceptance and retain the source and recovery evidence according to the agreed plan."], "A reconciled migration report with reviewed exceptions, provenance and acceptance.", "The customer has accepted the reconciled result and the approved retention and recovery requirements are met.", "Historical import, cross-module reconciliation and customer migration acceptance are not implemented."),
  ] },
  { id: "audit", title: "Prepare for an audit", summary: "Organize the planned evaluation, inspect evidence and identify the unresolved preparation work.", outcome: "A documented preparation review supported by the actual scope, evidence and open issues.", steps: [
    audits,
    { ...documents, id: "audit-information", title: "Review the information the audit will use", instructions: ["Identify the controlled documents and revisions relevant to the actual audit scope and criteria.", "Confirm availability and suitability with their owners; select the current released revision instead of a convenient unreviewed copy."] },
    implementations, risks,
    { id: "nonconformity-follow-up", title: "Review nonconformities and outstanding commitments", why: "Open issues and their containment or follow-up affect preparation and must remain visible.", instructions: ["Inspect nonconformities in the audit scope, their disposition and related risks or corrective actions.", "Verify containment, due dates and explicit closure decisions; a related closed CAPA does not close the incident automatically."], expected: "A reviewed list of open and closed issues with traceable follow-up.", doneWhen: "The responsible people have reviewed relevant issues and recorded follow-up and closure decisions where appropriate.", resource: "nonconformities", workspace: "nonconformities" },
    capas, management, execution,
  ] },
  { id: "expand", title: "Extend the scope or add sites", summary: "Bring new operations into the quality system while retaining local responsibility and evidence.", outcome: "A reviewed extension with clear boundaries, local implementation and an accepted updated scope.", steps: [
    { ...processes, id: "new-boundaries", title: "Identify the new operational boundaries", instructions: ["Select the organizational unit to inspect and identify the new site, products, services or processes.", "Review interfaces with existing processes and identify which responsibilities and information can be shared."] },
    normative, risks, documents, implementations, audits,
    pending("scope-acceptance", "Review local results and accept the extension", "Shared guidance does not remove local evidence, accountability or applicability decisions.", ["Review the new operations and their local evidence without combining unrelated site records.", "Document unresolved gaps and obtain acceptance of the updated organizational and normative scope."], "A reviewed extension decision with local evidence and an updated scope.", "Authorized reviewers have accepted the new boundaries and evaluated site-specific gaps and evidence.", "Project-wide scope expansion decisions, consolidated site readiness and formal updated baselines are not implemented."),
  ] },
];

export type GuideStepObservation = {
  kind: "feature_pending" | "choose_unit" | "loaded" | "restricted" | "unavailable";
  records: GuideRecord[]; qualified: number; limited: boolean; message: string;
};
const recordedSignals: Record<GuideResource, string> = {
  processes: "The highlighted signal is an active process record.",
  documents: "The highlighted signal is an active document with a recorded current revision; content still requires review.",
  implementations: "The highlighted signal is an active control implementation recorded as implemented; under-review work is not implemented.",
  risks: "The highlighted signal is a recorded closed risk; assessed or monitored risks are shown separately by their actual state.",
  nonconformities: "The highlighted signal is a recorded closed nonconformity.",
  capas: "The highlighted signal is a recorded closed CAPA, not automatic closure of its source.",
  audits: "Audit records reflect planning only. None is treated as an executed audit or a readiness approval.",
};

/** Observations describe existing records, never completion of a project or ISO requirement. */
export function observeGuideStep(step: GuideStep, snapshot: GuideSnapshot | null): GuideStepObservation {
  const empty = { records: [], qualified: 0, limited: false };
  if (step.productGap) return { ...empty, kind: "feature_pending", message: step.productGap };
  if (!snapshot || !step.resource) return { ...empty, kind: "choose_unit", message: "Choose an organizational unit to inspect the records you are authorized to read." };
  const resource = snapshot.resources[step.resource];
  if (resource.kind !== "loaded") return { ...empty, kind: resource.kind, message: resource.kind === "restricted" ? "A required read responsibility is not assigned in this unit. No absence or completion is inferred." : "The records could not be verified. No absence or completion is inferred." };
  return {
    kind: "loaded", records: resource.records, limited: resource.limited,
    qualified: resource.records.filter(record => record.qualified).length,
    message: `${recordedSignals[step.resource]} These unit records do not verify completion of a project step or ISO conformity.`,
  };
}
