/** Read-only planning copy; never an issued audit report or execution authorization. */
export type PlanSelection = { id: string; unit_id: string; row_version: number };
type Row = Record<string, unknown>;
export type AuditPlan = {
  audit: Row; company: string; unit: string; scopes: Row[]; criteria: Row[];
  team: Row[]; agenda: Row[]; generatedAt: string;
};
type Reader = (input: string, init: RequestInit) => Promise<Response>;
export class PlanExportError extends Error {
  constructor(message: string, readonly status?: number) { super(message); }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const isId = (value: unknown): value is string => typeof value === "string" && uuid.test(value);
const isText = (value: unknown): value is string => typeof value === "string" && value.length <= 4000;
const isVersion = (value: unknown): value is number => Number.isInteger(value) && Number(value) > 0;
const isRow = (value: unknown): value is Row => !!value && typeof value === "object" && !Array.isArray(value);
const invalid = () => new PlanExportError("The plan response could not be verified. Refresh the audit before downloading.");
const date = (value: unknown) => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
  && !Number.isNaN(Date.parse(value));
const instant = (value: unknown) => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value)
  && !Number.isNaN(Date.parse(value));
function auditValid(value: unknown, selection: PlanSelection): value is Row {
  return isRow(value) && value.id === selection.id && value.unit_id === selection.unit_id
    && value.row_version === selection.row_version && isId(value.tenant_id)
    && ["code", "name", "objective", "scope_summary", "state", "audit_type"].every(key => isText(value[key]))
    && date(value.planned_start) && date(value.planned_end)
    && (value.lead_auditor_user_id === null || isId(value.lead_auditor_user_id));
}
function childValid(row: unknown, kind: string, selection: PlanSelection): row is Row {
  if (!isRow(row) || !isId(row.id) || row.audit_id !== selection.id || row.unit_id !== selection.unit_id
    || !isVersion(row.row_version) || !["active", "withdrawn"].includes(String(row.status))
    || !isText(row.withdrawal_reason) || (row.status === "withdrawn" && !row.withdrawal_reason.trim())) return false;
  const fields = kind === "scopes" ? ["title", "description"] : kind === "criteria"
    ? ["title", "requirement", "source_type", "reference"] : kind === "team"
      ? ["display_name_snapshot", "responsibilities"] : ["title", "objective", "method", "location"];
  if (!fields.every(key => isText(row[key]))) return false;
  if (kind === "team") return isId(row.user_id) && ["auditor", "auditee"].includes(String(row.team_role));
  if (!Number.isInteger(row.sequence)) return false;
  if (kind === "scopes") return row.process_id === null || isId(row.process_id);
  if (row.scope_id !== null && !isId(row.scope_id)) return false;
  return kind !== "agenda" || (instant(row.starts_at) && instant(row.ends_at)
    && Date.parse(String(row.starts_at)) < Date.parse(String(row.ends_at))
    && isId(row.auditor_team_member_id) && (row.auditee_team_member_id === null || isId(row.auditee_team_member_id)));
}

/** Every page is checked; a changing parent/context or an oversized plan fails without a partial file. */
export async function collectAuditPlan(
  selection: PlanSelection, unit: string, signal: AbortSignal, reader: Reader = fetch,
): Promise<AuditPlan> {
  if (!isId(selection.id) || !isId(selection.unit_id) || !isVersion(selection.row_version) || !isText(unit)) throw invalid();
  const read = async (path: string): Promise<unknown> => {
    signal.throwIfAborted();
    const response = await reader("/api/identity" + path, { credentials: "include", cache: "no-store", signal });
    if (response.status !== 200) throw new PlanExportError(
      [401, 403, 404].includes(response.status)
        ? "Your audit access changed. Refresh the workspace before downloading."
        : "The plan could not be downloaded. Refresh and try again.", response.status,
    );
    return response.json();
  };
  const base = `/internal-audits/audits/${selection.id}`;
  const [identity, audit] = await Promise.all([read("/auth/me"), read(base)]);
  if (!isRow(identity) || !isId(identity.id) || !isId(identity.current_tenant_id)
    || !auditValid(audit, selection) || audit.tenant_id !== identity.current_tenant_id) throw invalid();
  const companies = await read("/auth/tenants");
  if (!Array.isArray(companies)) throw invalid();
  const company = companies.filter((row: unknown) => isRow(row) && row.id === identity.current_tenant_id);
  if (company.length !== 1 || !isRow(company[0]) || !isText(company[0].name)) throw invalid();
  const pages = async (kind: string): Promise<Row[]> => {
    const rows: Row[] = [], seen = new Set<string>();
    for (let offset = 0; offset <= 500; offset += 50) {
      const endpoint = kind === "team" ? "team-members" : kind;
      const page = await read(`${base}/${endpoint}?limit=50&offset=${offset}`);
      if (!Array.isArray(page) || page.length > 50) throw invalid();
      for (const row of page) {
        if (!childValid(row, kind, selection) || seen.has(String(row.id))) throw invalid();
        seen.add(String(row.id)); rows.push(row);
      }
      if (rows.length > 500) throw new PlanExportError("This plan exceeds 500 items in a section. No partial copy was downloaded.");
      if (page.length < 50) return rows;
    }
    throw invalid();
  };
  const [scopes, criteria, team, agenda] = await Promise.all([pages("scopes"), pages("criteria"), pages("team"), pages("agenda")]);
  const scopeIds = new Set(scopes.map(row => row.id)), teamIds = new Set(team.map(row => row.id));
  if (criteria.some(row => row.scope_id !== null && !scopeIds.has(row.scope_id))
    || agenda.some(row => (row.scope_id !== null && !scopeIds.has(row.scope_id))
      || !teamIds.has(row.auditor_team_member_id)
      || (row.auditee_team_member_id !== null && !teamIds.has(row.auditee_team_member_id)))) throw invalid();
  const [lastIdentity, lastAudit] = await Promise.all([read("/auth/me"), read(base)]);
  signal.throwIfAborted();
  if (!isRow(lastIdentity) || lastIdentity.id !== identity.id || lastIdentity.current_tenant_id !== identity.current_tenant_id
    || !auditValid(lastAudit, selection) || lastAudit.tenant_id !== audit.tenant_id
    || ["code", "name", "objective", "scope_summary", "state", "audit_type", "lead_auditor_user_id", "planned_start", "planned_end"].some(key => lastAudit[key] !== audit[key])) {
    throw new PlanExportError("The plan or company context changed. Refresh the audit before downloading.", 409);
  }
  return { audit, company: company[0].name, unit, scopes, criteria, team, agenda, generatedAt: new Date().toISOString() };
}

const escape = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, character => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]!
));
const words = (value: unknown) => escape(String(value ?? "").replaceAll("_", " "));
export function auditPlanFilename(plan: AuditPlan): string {
  const code = String(plan.audit.code).replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 60) || "audit";
  return `PerfectMatch-plan-${code}-v${Number(plan.audit.row_version)}.html`;
}
export function renderAuditPlan(plan: AuditPlan): string {
  const { audit, scopes, criteria, team, agenda } = plan;
  const person = (id: unknown) => team.find(row => row.id === id);
  const lead = team.find(row => row.user_id === audit.lead_auditor_user_id && row.status === "active" && row.team_role === "auditor");
  const scope = (id: unknown) => scopes.find(row => row.id === id)?.title ?? "Whole audit";
  const status = (row: Row) => `<span class="badge ${row.status === "withdrawn" ? "withdrawn" : ""}">${words(row.status)}</span>`;
  const reason = (row: Row) => row.status === "withdrawn" ? `<p class="withdrawal"><strong>Withdrawal reason</strong> ${escape(row.withdrawal_reason)}</p>` : "";
  const cards = (rows: Row[], content: (row: Row) => string) => rows.length ? rows.map(row => `<article class="item">${content(row)}${reason(row)}</article>`).join("") : '<p class="empty">No items recorded.</p>';
  const title = (number: string, label: string, rows: Row[]) => `<h2><span>${number}</span>${label}</h2><p class="counts">${rows.filter(row => row.status === "active").length} active · ${rows.filter(row => row.status === "withdrawn").length} withdrawn</p>`;
  const time = (value: unknown) => escape(new Date(String(value)).toISOString().replace("T", " ").replace(".000Z", " UTC"));
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><meta name="referrer" content="no-referrer"><title>${escape(audit.code)} · Audit plan · Perfect Match QMS</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf3f8;color:#172d45;font:15px/1.6 Inter,ui-sans-serif,system-ui,sans-serif}main{max-width:960px;margin:40px auto;background:white;padding:48px;border-top:5px solid #087f82;border-radius:8px;box-shadow:0 12px 45px #172d4510}.brand{font-weight:800;letter-spacing:.02em;font-size:18px}.brand small{font-size:12px;color:#526579;font-weight:500}.eyebrow{margin-top:40px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#087276;font-weight:750}h1{font-size:clamp(25px,4vw,38px);line-height:1.2;margin:10px 0 18px}h2{font-size:21px;display:flex;gap:12px;align-items:center;margin:0}h2 span{font-size:12px;color:#087276;background:#e6f4f2;padding:5px 9px;border-radius:5px}h3{font-size:16px;margin:0}p{white-space:pre-wrap;overflow-wrap:anywhere}section{margin-top:32px;border-top:1px solid #d8e2ed;padding-top:24px}.notice{background:#f2f6fa;border-left:3px solid #087f82;padding:16px;font-size:13px}.notice strong{display:block}.meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 24px;margin:24px 0}dt{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#526579}dd{margin:3px 0 0;font-weight:600;overflow-wrap:anywhere}.item{padding:18px 0;border-bottom:1px solid #e4ebf2;break-inside:avoid}.item header{display:flex;justify-content:space-between;align-items:start;gap:12px}.item p{margin:8px 0}.badge{font-size:11px;font-weight:700;border:1px solid #b6dcd7;background:#edf9f6;color:#15604c;padding:2px 8px;border-radius:20px;white-space:nowrap}.withdrawn{color:#714500;background:#fff4df;border-color:#e9ca94}.counts,.empty,.detail{font-size:12px;color:#526579}.counts{margin:8px 0 0}.withdrawal{padding:10px 12px;background:#fff8eb;color:#714500;font-size:12px}footer{margin-top:36px;padding-top:20px;border-top:2px solid #172d45;color:#526579;font-size:11px;overflow-wrap:anywhere}footer p{margin:5px 0}@media(max-width:600px){main{margin:0;padding:24px 20px;border-radius:0}.meta{grid-template-columns:1fr}.item header{flex-wrap:wrap}}@media print{@page{size:A4;margin:16mm}body{background:white;font-size:10pt}main{padding:0;margin:0;max-width:none;border-radius:0;box-shadow:none}.eyebrow{margin-top:24px}h2,h3{break-after:avoid}section{break-before:auto}.item{break-inside:auto}p{orphans:3;widows:3}.notice,.meta{break-inside:avoid}}
</style></head><body><main><header><div class="brand">Perfect Match <small>QMS</small></div><p class="eyebrow">Audit planning · ${escape(audit.code)}</p><h1>${escape(audit.name)}</h1><p class="detail">${escape(plan.company)} · ${escape(plan.unit)}</p><div class="notice"><strong>Planning copy · Not an issued audit report</strong>State: ${words(audit.state)} · Plan version ${escape(audit.row_version)}. This copy does not confirm readiness, execution, findings or certification.</div></header>
<dl class="meta"><div><dt>Planned dates</dt><dd>${escape(audit.planned_start)} — ${escape(audit.planned_end)}</dd></div><div><dt>Audit type</dt><dd>${words(audit.audit_type)}</dd></div><div><dt>Lead auditor</dt><dd>${lead ? escape(lead.display_name_snapshot) : "Not assigned to an active planned auditor"}</dd></div><div><dt>Generated (UTC)</dt><dd>${time(plan.generatedAt)}</dd></div></dl>
<section><h2><span>01</span>Objective & scope</h2><p>${escape(audit.objective)}</p><p>${escape(audit.scope_summary)}</p>${cards(scopes, row => `<header><h3>${escape(row.sequence)} · ${escape(row.title)}</h3>${status(row)}</header><p>${escape(row.description)}</p>`)}</section>
<section>${title("02", "Audit criteria", criteria)}${cards(criteria, row => `<header><h3>${escape(row.sequence)} · ${escape(row.title)}</h3>${status(row)}</header><p>${escape(row.requirement)}</p><p class="detail">${words(row.source_type)} · ${escape(row.reference)}<br>Scope: ${escape(scope(row.scope_id))}</p>`)}</section>
<section>${title("03", "Planned team", team)}${cards(team, row => `<header><h3>${escape(row.display_name_snapshot)}</h3>${status(row)}</header><p class="detail">${words(row.team_role)}</p><p>${escape(row.responsibilities)}</p>`)}</section>
<section>${title("04", "Agenda (UTC)", agenda)}${cards(agenda, row => `<header><h3>${escape(row.sequence)} · ${escape(row.title)}</h3>${status(row)}</header><p>${time(row.starts_at)} — ${time(row.ends_at)}</p><p>${escape(row.objective)}</p><p class="detail">Auditor: ${escape(person(row.auditor_team_member_id)?.display_name_snapshot)}<br>Auditee: ${escape(person(row.auditee_team_member_id)?.display_name_snapshot ?? "Not assigned")}<br>Scope: ${escape(scope(row.scope_id))}<br>Method: ${escape(row.method)} · Location: ${escape(row.location)}</p>`)}</section>
<footer><p>Perfect Match QMS · Audit ${escape(audit.code)} · Version ${escape(audit.row_version)} · Reference ${escape(audit.id)}</p><p>Downloaded copies do not update. Verify the current plan in your company workspace.</p><p>Print or save as PDF using your browser. Assessment rationale, competence documents, technical logs and execution results are not included.</p></footer></main></body></html>`;
}
