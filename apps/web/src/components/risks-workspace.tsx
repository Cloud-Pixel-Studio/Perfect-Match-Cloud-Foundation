"use client";

import { ChartNoAxesCombined, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { RiskLinks } from "./risk-links";
import { RelatedCAPAs } from "./related-capas";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Unit = { id: string; code: string; name: string; status: string };
type Process = { id: string; code: string; name: string; status: string };
type Member = { id: string; display_name: string };
type Risk = {
  id: string; unit_id: string; process_id: string; code: string; name: string;
  risk_type: string; category: string; source: string; description: string; cause: string;
  potential_effect: string; benefit: string; opportunity_action: string; mitigation_plan: string;
  owner_user_id: string | null; likelihood: number; impact: number;
  residual_likelihood: number; residual_impact: number; response_strategy: string;
  target_date: string | null; review_date: string | null; state: string; row_version: number;
  closure_notes: string; scoring_model: string; initial_score: number; initial_level: string;
  residual_score: number; residual_level: string; is_overdue: boolean; days_overdue: number;
  assessed_at: string | null; reviewed_at: string | null; closed_at: string | null;
};
const api = "/api/identity";
const categories = ["strategic", "operational", "process", "supplier", "document", "customer", "security", "other"];
const strategies = ["accept", "mitigate", "transfer", "avoid", "exploit", "enhance", "share"];
const states = ["draft", "assessed", "action_required", "monitoring", "closed"];
const transitions: Record<string, string[]> = {
  draft: ["assessed"], assessed: ["action_required", "monitoring"],
  action_required: ["monitoring"], monitoring: ["monitoring", "action_required", "closed"], closed: [],
};
const label = (value: string) => value.replaceAll("_", " ");
const dateLabel = (value: string | null) => value ? new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium", timeZone: /^\d{4}-\d{2}-\d{2}$/.test(value) ? "UTC" : undefined,
}).format(new Date(value)) : "Not recorded";

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as T;
}

function errorMessage(cause: unknown) {
  if (cause instanceof Error && ["401", "403"].includes(cause.message)) return "Your access changed. Refresh your permissions or sign in again.";
  if (cause instanceof Error && cause.message === "409") return "The record or its workflow changed. Refresh and review the latest version before trying again.";
  if (cause instanceof Error && cause.message === "422") return "Review the required fields, dates and scores before saving.";
  return "The risk register could not be reached. Try refreshing.";
}

function RiskFields({ risk, members, processes }: { risk?: Risk; members: Member[]; processes: Process[] }) {
  const [ownerId, setOwnerId] = useState(risk?.owner_user_id ?? "");
  const [ownerLabel, setOwnerLabel] = useState("Current responsible person");
  const [processId, setProcessId] = useState("");
  const [processLabel, setProcessLabel] = useState("Selected process");
  return <>
    {!risk && <><label>Code<input name="code" required maxLength={40} /></label>
      <label>Process<select name="process_id" value={processId} required onChange={(event) => { const id = event.target.value; setProcessId(id); const process = processes.find((item) => item.id === id); if (process) setProcessLabel(`${process.code} · ${process.name}`); }}><option value="">Select an active process</option>{processId && !processes.some((item) => item.id === processId && item.status === "active") && <option value={processId}>{processLabel}</option>}{processes.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label></>}
    <label>Name<input name="name" defaultValue={risk?.name ?? ""} required maxLength={160} /></label>
    <label>Type<select name="risk_type" defaultValue={risk?.risk_type ?? "risk"}><option value="risk">Risk</option><option value="opportunity">Opportunity</option></select></label>
    <label>Category<select name="category" defaultValue={risk?.category ?? "operational"}>{categories.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
    <label>Responsible person<select name="owner_user_id" value={ownerId} onChange={(event) => { const id = event.target.value; setOwnerId(id); const member = members.find((item) => item.id === id); if (member) setOwnerLabel(member.display_name); }}><option value="">Unassigned</option>{ownerId && !members.some((member) => member.id === ownerId) && <option value={ownerId}>{ownerLabel}</option>}{members.map((member) => <option key={member.id} value={member.id}>{member.display_name}</option>)}</select></label>
    <label className="process-wide-field">Description<textarea name="description" defaultValue={risk?.description ?? ""} required maxLength={4000} rows={3} /></label>
    <label>Source<input name="source" defaultValue={risk?.source ?? ""} maxLength={200} /></label>
    <label>Response strategy<select name="response_strategy" defaultValue={risk?.response_strategy ?? "mitigate"}>{strategies.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
    {(["likelihood", "impact", "residual_likelihood", "residual_impact"] as const).map((name) => <label key={name}>{label(name)} (1–5)<input name={name} type="number" min={1} max={5} step={1} required defaultValue={risk?.[name] ?? 1} /></label>)}
    <label>Target date<input name="target_date" type="date" defaultValue={risk?.target_date ?? ""} /></label>
    <label>Next review<input name="review_date" type="date" defaultValue={risk?.review_date ?? ""} /></label>
    <details className="control-guidance-editor process-wide-field"><summary>Cause, effect, opportunity and response details</summary><div className="control-guidance-fields">
      {(["cause", "potential_effect", "benefit", "opportunity_action", "mitigation_plan", "closure_notes"] as const).map((name) => <label key={name}>{label(name)}<textarea name={name} defaultValue={risk?.[name] ?? ""} maxLength={4000} rows={3} /></label>)}
    </div></details>
  </>;
}

export function RisksWorkspace({ onAccessDenied, preferredUnitId, onUnitChange }: { onAccessDenied?: () => void; preferredUnitId?: string; onUnitChange?: (unitId: string) => void }) {
  const [initialPreferredUnitId] = useState(preferredUnitId ?? "");
  const [units, setUnits] = useState<Unit[]>([]);
  const [unitId, setUnitId] = useState("");
  const [caps, setCaps] = useState<string[]>([]);
  const [rows, setRows] = useState<Risk[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [query, setQuery] = useState({ q: "", state: "", risk_type: "", offset: 0 });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [processes, setProcesses] = useState<Process[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [memberNames, setMemberNames] = useState<Record<string, string>>({});
  const [processNames, setProcessNames] = useState<Record<string, string>>({});
  const [processSearch, setProcessSearch] = useState("");
  const [memberSearch, setMemberSearch] = useState("");
  const [processOffset, setProcessOffset] = useState(0);
  const [memberOffset, setMemberOffset] = useState(0);
  const [referenceBusy, setReferenceBusy] = useState(false);
  const [transitionTarget, setTransitionTarget] = useState("");
  const epoch = useRef(0);
  const mutation = useRef(0);
  const denied = useRef(onAccessDenied);
  const canRead = caps.includes("risks.read");
  const canManage = canRead && caps.includes("risks.manage");
  const canReview = canRead && caps.includes("risks.review");
  const canReadProcesses = caps.includes("processes.read");
  const selected = rows.find((row) => row.id === selectedId);

  useEffect(() => { denied.current = onAccessDenied; }, [onAccessDenied]);
  useEffect(() => {
    const requestEpoch = epoch;
    const mutationEpoch = mutation;
    const controller = new AbortController();
    void read<Unit[]>("/organization/units?limit=100", controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      const active = data.filter((unit) => unit.status === "active");
      const nextUnit = active.find((unit) => unit.id === initialPreferredUnitId)?.id ?? active[0]?.id ?? "";
      setUnits(active); setUnitId(nextUnit);
      if (!active.length) setLoading(false);
    }).catch((cause) => { if (!controller.signal.aborted) { setError(errorMessage(cause)); setLoading(false); } });
    return () => { controller.abort(); ++requestEpoch.current; ++mutationEpoch.current; };
  }, [initialPreferredUnitId]);

  const invalidate = useCallback(() => {
    ++epoch.current; ++mutation.current;
    setCaps([]); setRows([]); setSelectedId(""); setCreating(false); setEditing(false);
    setProcesses([]); setMembers([]); setMemberNames({}); setProcessNames({}); setError(""); setNotice(""); setLoading(true);
  }, []);

  useEffect(() => {
    const revision = ++epoch.current;
    const controller = new AbortController();
    if (!unitId) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setLoading(true); setError("");
      void read<{ capabilities: string[] }>(`/qms-access/effective?unit_id=${encodeURIComponent(unitId)}`, controller.signal).then(async (access) => {
        if (revision !== epoch.current || controller.signal.aborted) return;
        setCaps(access.capabilities);
        if (!access.capabilities.includes("risks.read")) { setRows([]); setSelectedId(""); return; }
        const params = new URLSearchParams({ unit_id: unitId, q: query.q, limit: "50", offset: String(query.offset) });
        if (query.state) params.set("state", query.state);
        if (query.risk_type) params.set("risk_type", query.risk_type);
        const data = await read<Risk[]>(`/risks?${params}`, controller.signal);
        if (revision !== epoch.current || controller.signal.aborted) return;
        setRows(data); setSelectedId((current) => data.some((row) => row.id === current) ? current : data[0]?.id ?? "");
      }).catch((cause) => {
        if (revision !== epoch.current || controller.signal.aborted) return;
        setRows([]); setSelectedId(""); setError(errorMessage(cause));
        if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); denied.current?.(); }
      }).finally(() => { if (revision === epoch.current && !controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, query, refresh]);

  useEffect(() => {
    const controller = new AbortController();
    if (!unitId || !canManage || (!creating && !editing)) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setReferenceBusy(true);
      const processQuery = new URLSearchParams({ unit_id: unitId, limit: "50", offset: String(processOffset), search: processSearch });
      const memberQuery = new URLSearchParams({ limit: "50", offset: String(memberOffset), search: memberSearch });
      void Promise.all([
        creating && canReadProcesses ? read<Process[]>(`/processes?${processQuery}`, controller.signal) : Promise.resolve([]),
        read<Member[]>(`/organization/members?${memberQuery}`, controller.signal),
      ]).then(([nextProcesses, nextMembers]) => {
        if (!controller.signal.aborted) {
          setProcesses(nextProcesses); setMembers(nextMembers);
          setProcessNames((current) => ({ ...current, ...Object.fromEntries(nextProcesses.map((item) => [item.id, `${item.code} · ${item.name}`])) }));
          setMemberNames((current) => ({ ...current, ...Object.fromEntries(nextMembers.map((item) => [item.id, item.display_name])) }));
        }
      }).catch((cause) => { if (!controller.signal.aborted) { setProcesses([]); setMembers([]); setError(errorMessage(cause)); } })
        .finally(() => { if (!controller.signal.aborted) setReferenceBusy(false); });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, canManage, canReadProcesses, creating, editing, processSearch, memberSearch, processOffset, memberOffset]);

  useEffect(() => {
    const controller = new AbortController();
    if (!canRead || !selected) return () => controller.abort();
    void read<Member[]>("/organization/members?limit=100", controller.signal).then((data) => {
      if (!controller.signal.aborted) setMemberNames((current) => ({ ...current, ...Object.fromEntries(data.map((item) => [item.id, item.display_name])) }));
    }).catch(() => { /* Keep readable fallback when the directory is unavailable. */ });
    if (canReadProcesses) void read<Process>(`/processes/${selected.process_id}`, controller.signal).then((process) => {
      if (!controller.signal.aborted) setProcessNames((current) => ({ ...current, [process.id]: `${process.code} · ${process.name}` }));
    }).catch(() => { /* Risk read access does not grant access to its linked process. */ });
    return () => controller.abort();
  }, [canRead, canReadProcesses, selected]);

  async function save(path: string, method: "POST" | "PATCH", body: object) {
    const revision = epoch.current;
    const attempt = ++mutation.current;
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}${path}`, { method, credentials: "include", headers: {
        "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "",
      }, body: JSON.stringify(body) });
      if (revision !== epoch.current || attempt !== mutation.current) return;
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json() as Risk;
      if (revision !== epoch.current || attempt !== mutation.current) return;
      setCreating(false); setEditing(false); setSelectedId(result.id);
      if (method === "POST" && path === "/risks") {
        setSearch(result.code); setStateFilter(""); setTypeFilter("");
        setQuery({ q: result.code, state: "", risk_type: "", offset: 0 });
      }
      setRows((current) => current.some((row) => row.id === result.id) ? current.map((row) => row.id === result.id ? result : row) : current);
      setTransitionTarget(""); setNotice("Saved. The change is recorded in the audit trail.");
      setRefresh((current) => current + 1);
    } catch (cause) {
      if (revision !== epoch.current || attempt !== mutation.current) return;
      setError(errorMessage(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); setRows([]); setSelectedId(""); denied.current?.(); }
    } finally { if (attempt === mutation.current) setBusy(false); }
  }

  async function submitRisk(event: React.FormEvent<HTMLFormElement>, risk?: Risk) {
    event.preventDefault(); if (!canManage || busy || (!risk && !canReadProcesses)) return;
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {};
    for (const field of ["name", "risk_type", "category", "source", "description", "cause", "potential_effect", "benefit", "opportunity_action", "mitigation_plan", "closure_notes", "response_strategy"]) body[field] = String(data.get(field) ?? "");
    for (const field of ["likelihood", "impact", "residual_likelihood", "residual_impact"]) body[field] = Number(data.get(field));
    for (const field of ["target_date", "review_date", "owner_user_id"]) body[field] = data.get(field) || null;
    if (risk) body.expected_version = risk.row_version;
    else { body.code = data.get("code"); body.process_id = data.get("process_id"); body.unit_id = unitId; }
    await save(risk ? `/risks/${risk.id}` : "/risks", risk ? "PATCH" : "POST", body);
  }

  function referenceSearch() {
    return <div className="risk-reference-search">
      {creating && <div><label>Find a process<input maxLength={160} value={processSearch} onChange={(event) => { setProcessSearch(event.target.value); setProcessOffset(0); }} /></label><nav aria-label="Risk process search pages"><button type="button" disabled={referenceBusy || processOffset === 0} onClick={() => setProcessOffset(Math.max(0, processOffset - 50))}>Previous processes</button><button type="button" disabled={referenceBusy || processes.length < 50 || processOffset >= 1_000_000} onClick={() => setProcessOffset(processOffset + 50)}>More processes</button></nav></div>}
      <div><label>Find a responsible person<input maxLength={160} value={memberSearch} onChange={(event) => { setMemberSearch(event.target.value); setMemberOffset(0); }} /></label><nav aria-label="Risk member search pages"><button type="button" disabled={referenceBusy || memberOffset === 0} onClick={() => setMemberOffset(Math.max(0, memberOffset - 50))}>Previous people</button><button type="button" disabled={referenceBusy || members.length < 50 || memberOffset >= 1_000_000} onClick={() => setMemberOffset(memberOffset + 50)}>More people</button></nav></div>
    </div>;
  }

  return <section className="risks-panel" aria-labelledby="risks-heading" aria-busy={loading || busy}>
    <div className="workspace-heading"><div><p className="eyebrow">Process resilience</p><h2 id="risks-heading"><ChartNoAxesCombined aria-hidden="true" size={22} /> Risks & opportunities</h2><p className="workspace-subtitle">Assess exposure, plan a response and keep each review traceable.</p></div><button className="secondary-action compact-action" type="button" disabled={loading || busy || !unitId} onClick={() => { setEditing(false); setRefresh((current) => current + 1); }}><RefreshCw size={16} aria-hidden="true" /> Refresh risks</button></div>
    <fieldset className="risk-toolbar" disabled={busy}><label>Organization scope<select value={unitId} onChange={(event) => { invalidate(); setUnitId(event.target.value); onUnitChange?.(event.target.value); setSearch(""); setStateFilter(""); setTypeFilter(""); setQuery({ q: "", state: "", risk_type: "", offset: 0 }); }}><option value="">Select a unit</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.code} · {unit.name}</option>)}</select></label>
      {canRead && <form onSubmit={(event) => { event.preventDefault(); setEditing(false); setQuery({ q: search.trim(), state: stateFilter, risk_type: typeFilter, offset: 0 }); }}><label>Find by code or name<input value={search} maxLength={160} onChange={(event) => setSearch(event.target.value)} /></label><label>Status<select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}><option value="">All statuses</option>{states.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label><label>Type<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Risks and opportunities</option><option value="risk">Risks</option><option value="opportunity">Opportunities</option></select></label><button className="secondary-action compact-action" type="submit" disabled={loading}>Search risks</button></form>}
    </fieldset>
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {loading ? <RecordWorkspaceSkeleton label="Loading risk access and records" /> : !unitId ? <p className="risk-empty">Select an active organization unit.</p> : !canRead ? <p className="risk-empty">No risk read responsibility is assigned for this unit. Contact the organization owner.</p> : <>
      {canManage && <div className="risk-create-action"><button className="primary-action compact-action" disabled={busy || !canReadProcesses} type="button" onClick={() => { setCreating((value) => !value); setEditing(false); }}><Plus size={16} aria-hidden="true" /> New risk or opportunity</button>{!canReadProcesses && <p className="qms-history-caption">Process read responsibility is needed to register a risk against an active process.</p>}</div>}
      {creating && canManage && <form className="process-editor risk-editor" onSubmit={(event) => void submitRisk(event)}><h3>Register a risk or opportunity</h3>{referenceSearch()}<fieldset disabled={busy || referenceBusy}><RiskFields members={members} processes={processes} /><button className="primary-action compact-action" type="submit">Register</button><button className="secondary-action compact-action" type="button" onClick={() => setCreating(false)}>Cancel</button></fieldset></form>}
      <div className="risk-register-grid"><aside aria-label="Risk register"><h3>Register <span>{rows.length}</span></h3>{rows.length ? <ul>{rows.map((row) => <li key={row.id}><button type="button" disabled={busy} aria-pressed={row.id === selectedId} onClick={() => { setSelectedId(row.id); setEditing(false); setTransitionTarget(""); setError(""); }}><span><strong>{row.code}</strong><small>{label(row.state)} · {label(row.risk_type)}</small></span><span>{row.name}</span>{row.is_overdue && <small className="risk-overdue">{row.days_overdue} days overdue</small>}</button></li>)}</ul> : <p className="risk-empty">No records match this scope and search.</p>}<nav className="risk-pagination" aria-label="Risk register pages"><button type="button" disabled={busy || query.offset === 0} onClick={() => { setEditing(false); setQuery({ ...query, offset: Math.max(0, query.offset - 50) }); }}>Previous</button><span>Page {Math.floor(query.offset / 50) + 1}</span><button type="button" disabled={busy || rows.length < 50 || query.offset >= 1_000_000} onClick={() => { setEditing(false); setQuery({ ...query, offset: query.offset + 50 }); }}>Next</button></nav></aside>
        <div>{selected ? <article className="risk-detail" key={`${selected.id}-${selected.row_version}`}><div className="risk-detail-heading"><div><p className="eyebrow">{selected.code} · {label(selected.risk_type)}</p><h3>{selected.name}</h3></div><span className="process-status">{label(selected.state)}</span></div>
          <div className="risk-score-grid"><div><small>Initial exposure</small><strong>{selected.initial_score}<span>/25</span></strong><span className={`risk-level ${selected.initial_level}`}>{label(selected.initial_level)}</span></div><div><small>Residual exposure</small><strong>{selected.residual_score}<span>/25</span></strong><span className={`risk-level ${selected.residual_level}`}>{label(selected.residual_level)}</span></div></div>
          <p className="qms-history-caption">5 × 5 assessment: probability × impact. Low 1–4, moderate 5–9, high 10–15, critical 16–25. Method: {selected.scoring_model}.</p>
          <p className="control-description">{selected.description}</p><dl className="risk-metadata"><div><dt>Process</dt><dd>{processNames[selected.process_id] ?? "Linked process"}</dd></div><div><dt>Responsible person</dt><dd>{selected.owner_user_id ? (memberNames[selected.owner_user_id] ?? "Assigned member") : "Unassigned"}</dd></div><div><dt>Response</dt><dd>{label(selected.response_strategy)}</dd></div><div><dt>Category</dt><dd>{label(selected.category)}</dd></div><div><dt>Target</dt><dd>{dateLabel(selected.target_date)}</dd></div><div><dt>Next review</dt><dd>{dateLabel(selected.review_date)}</dd></div><div><dt>Assessed</dt><dd>{dateLabel(selected.assessed_at)}</dd></div><div><dt>Last review</dt><dd>{dateLabel(selected.reviewed_at)}</dd></div><div><dt>Closed</dt><dd>{dateLabel(selected.closed_at)}</dd></div></dl>
          <details className="control-guidance-read"><summary>Assessment and response details</summary><dl>{(["source", "cause", "potential_effect", "benefit", "opportunity_action", "mitigation_plan", "closure_notes"] as const).map((name) => <div key={name}><dt>{label(name)}</dt><dd>{selected[name] || "Not recorded"}</dd></div>)}</dl></details>
          <RelatedCAPAs key={`capa-${selected.id}-${selected.unit_id}-${selected.process_id}`} origin={{ ...selected, kind: "risk" }} capabilities={caps} disabled={busy || editing || creating} onBusyChange={setBusy}
            onAccessChanged={() => { invalidate(); setRefresh((value) => value + 1); denied.current?.(); }} />
          <RiskLinks risk={selected} capabilities={caps} disabled={busy || editing} onBusyChange={setBusy}
            onVersionChange={(version) => setRows((current) => current.map((row) => row.id === selected.id ? { ...row, row_version: version } : row))}
            onRefresh={() => { setEditing(false); setRefresh((value) => value + 1); }} />
          {canManage && selected.state !== "closed" && <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setEditing((value) => !value)}>{editing ? "Cancel editing" : "Edit assessment"}</button>}
          {editing && canManage && selected.state !== "closed" && <form className="process-editor risk-editor" onSubmit={(event) => void submitRisk(event, selected)}><h4>Edit {selected.code}</h4>{referenceSearch()}<fieldset disabled={busy || referenceBusy}><RiskFields risk={selected} members={members} processes={processes} /><button className="primary-action compact-action" type="submit">Save assessment</button></fieldset></form>}
          {canReview && selected.state !== "closed" && <form className="risk-transition" onSubmit={(event) => { event.preventDefault(); if (busy) return; const data = new FormData(event.currentTarget); const target = String(data.get("target_state")); void save(`/risks/${selected.id}/transition`, "POST", { expected_version: selected.row_version, target_state: target, decision: data.get("decision"), ...(target === "closed" ? { closure_notes: data.get("closure_notes") } : {}) }); }}><h4>Review and workflow</h4><fieldset disabled={busy}><label>Action<select name="target_state" value={transitionTarget || transitions[selected.state]?.[0] || ""} onChange={(event) => setTransitionTarget(event.target.value)}>{transitions[selected.state]?.map((value) => <option key={value} value={value}>{value === selected.state ? "Record monitoring review" : `Move to ${label(value)}`}</option>)}</select></label><label>Decision<textarea name="decision" required maxLength={500} rows={2} /></label>{(transitionTarget || transitions[selected.state]?.[0]) === "closed" && <label>Closure notes<textarea name="closure_notes" defaultValue={selected.closure_notes} required maxLength={4000} rows={3} /></label>}<button className="secondary-action compact-action" type="submit">Record decision</button></fieldset></form>}
          {selected.state === "closed" && <p className="qms-history-caption">This closed record is preserved for traceability.</p>}
        </article> : <div className="risk-empty"><strong>Select a record</strong><p>Review its exposure, response and current workflow.</p></div>}</div>
      </div>
    </>}
  </section>;
}
