"use client";

import { AlertTriangle, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { NCRLinks } from "./ncr-links";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";
import { RelatedCAPAs } from "./related-capas";

type Unit = { id: string; code: string; name: string; status: string };
type Process = { id: string; code: string; name: string; status: string };
type Member = { id: string; display_name: string };
type Nonconformity = {
  id: string; unit_id: string; process_id: string; code: string; name: string;
  source_type: string; severity: string; description: string; detected_date: string;
  detected_by_user_id: string; owner_user_id: string | null; target_date: string | null;
  containment_required: boolean; containment_action: string;
  containment_owner_user_id: string | null; containment_date: string | null;
  containment_completed: boolean; disposition: string | null; disposition_notes: string;
  root_cause_summary: string; closure_notes: string; cancellation_reason: string;
  state: string; row_version: number; is_overdue: boolean; days_overdue: number;
  opened_by_user_id: string | null; opened_at: string | null;
  reviewed_by_user_id: string | null; reviewed_at: string | null;
  closed_by_user_id: string | null; closed_at: string | null;
  cancelled_by_user_id: string | null; cancelled_at: string | null;
};
const api = "/api/identity";
const sources = ["internal", "customer", "supplier", "process", "product", "document", "audit", "other"];
const severities = ["minor", "major", "critical"];
const dispositions = ["use_as_is", "rework", "repair", "return", "scrap", "information_only", "other"];
const states = ["draft", "open", "containment", "investigation", "action_required", "verification", "closed", "cancelled"];
const transitions: Record<string, string[]> = {
  draft: ["open", "cancelled"], open: ["containment", "investigation", "cancelled"],
  containment: ["investigation", "cancelled"], investigation: ["action_required", "cancelled"],
  action_required: ["verification", "closed", "cancelled"], verification: ["closed", "cancelled"],
  closed: [], cancelled: [],
};
const label = (value: string) => value.replaceAll("_", " ");
const terminal = (value: string) => value === "closed" || value === "cancelled";
const dateLabel = (value: string | null) => value ? new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium", timeZone: /^\d{4}-\d{2}-\d{2}$/.test(value) ? "UTC" : undefined,
}).format(new Date(value)) : "Not recorded";

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as T;
}

function errorMessage(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : "";
  if (["401", "403"].includes(code)) return "Your access changed. Refresh your permissions or sign in again.";
  if (code === "409") return "The record or its workflow changed. Refresh and review the latest version before trying again.";
  if (code === "422") return "Review the required fields and containment details before saving.";
  if (code === "404") return "This record is no longer available with your access. Refresh the register.";
  return "The nonconformity register could not be reached. Try refreshing.";
}

function PersonSelect({ name, title, value, members, names }: {
  name: string; title: string; value?: string | null; members: Member[]; names: Record<string, string>;
}) {
  const [chosen, setChosen] = useState(value ?? "");
  const [chosenLabel, setChosenLabel] = useState(value ? names[value] ?? "Assigned member" : "");
  return <label>{title}<select name={name} value={chosen} onChange={(event) => {
    const id = event.target.value;
    setChosen(id);
    setChosenLabel(members.find((member) => member.id === id)?.display_name ?? "Selected member");
  }}><option value="">Unassigned</option>
    {chosen && !members.some((member) => member.id === chosen) && <option value={chosen}>{names[chosen] ?? chosenLabel}</option>}
    {members.map((member) => <option key={member.id} value={member.id}>{member.display_name}</option>)}
  </select></label>;
}

function NCRFields({ record, members, memberNames, processes }: {
  record?: Nonconformity; members: Member[]; memberNames: Record<string, string>; processes: Process[];
}) {
  const [processId, setProcessId] = useState("");
  const [processLabel, setProcessLabel] = useState("Selected process");
  const [containmentRequired, setContainmentRequired] = useState(record?.containment_required ?? false);
  const [containmentCompleted, setContainmentCompleted] = useState(record?.containment_completed ?? false);
  const requiredLocked = !!record && record.state !== "draft" && record.containment_required;
  return <>
    <fieldset className="ncr-form-section"><legend>Identification and detection</legend><div className="ncr-form-grid">
      {!record && <>
        <label>Code<input name="code" required maxLength={40} /></label>
        <label>Process<select name="process_id" value={processId} required onChange={(event) => {
          const id = event.target.value; setProcessId(id);
          const selected = processes.find((process) => process.id === id);
          if (selected) setProcessLabel(`${selected.code} · ${selected.name}`);
        }}><option value="">Select an active process</option>
          {processId && !processes.some((process) => process.id === processId && process.status === "active") && <option value={processId}>{processLabel}</option>}
          {processes.filter((process) => process.status === "active").map((process) => <option key={process.id} value={process.id}>{process.code} · {process.name}</option>)}
        </select></label>
      </>}
      <label className="ncr-wide">Title<input name="name" defaultValue={record?.name ?? ""} required maxLength={160} /></label>
      <label>Source<select name="source_type" defaultValue={record?.source_type ?? "internal"}>{sources.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <label>Severity<select name="severity" defaultValue={record?.severity ?? "minor"}>{severities.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <label className="ncr-wide">Description<textarea name="description" defaultValue={record?.description ?? ""} required maxLength={4000} rows={3} /></label>
      <label>Detected on<input type="date" name="detected_date" required defaultValue={record?.detected_date ?? new Date().toISOString().slice(0, 10)} /></label>
      <label>Target date<input type="date" name="target_date" defaultValue={record?.target_date ?? ""} /></label>
      <PersonSelect name="owner_user_id" title="Responsible person" value={record?.owner_user_id} members={members} names={memberNames} />
    </div></fieldset>
    <fieldset className="ncr-form-section"><legend>Containment</legend><div className="ncr-form-grid">
      <label className="ncr-check"><input type="checkbox" checked={containmentRequired} disabled={requiredLocked} onChange={(event) => setContainmentRequired(event.target.checked)} /> Containment required</label>
      <input type="hidden" name="containment_required" value={String(containmentRequired)} />
      <label className="ncr-check"><input type="checkbox" checked={containmentCompleted} onChange={(event) => setContainmentCompleted(event.target.checked)} /> Containment completed</label>
      <input type="hidden" name="containment_completed" value={String(containmentCompleted)} />
      {requiredLocked && <p className="qms-history-caption ncr-wide">Required containment remains part of this record after opening.</p>}
      <label className="ncr-wide">Containment action<textarea name="containment_action" defaultValue={record?.containment_action ?? ""} maxLength={4000} rows={3} required={containmentCompleted} /></label>
      <PersonSelect name="containment_owner_user_id" title="Containment responsible person" value={record?.containment_owner_user_id} members={members} names={memberNames} />
      <label>Containment completed on<input type="date" name="containment_date" defaultValue={record?.containment_date ?? ""} required={containmentCompleted} /></label>
      {containmentCompleted && <p className="qms-history-caption ncr-wide">Record the action and completion date to confirm containment.</p>}
    </div></fieldset>
    <fieldset className="ncr-form-section"><legend>Investigation, disposition and closure</legend><div className="ncr-form-grid">
      <label className="ncr-wide">Root cause summary<textarea name="root_cause_summary" defaultValue={record?.root_cause_summary ?? ""} maxLength={4000} rows={3} /></label>
      <label>Disposition<select name="disposition" defaultValue={record?.disposition ?? ""}><option value="">Not decided</option>{dispositions.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <label className="ncr-wide">Disposition notes<textarea name="disposition_notes" defaultValue={record?.disposition_notes ?? ""} maxLength={4000} rows={3} /></label>
      <label className="ncr-wide">Closure notes<textarea name="closure_notes" defaultValue={record?.closure_notes ?? ""} maxLength={4000} rows={3} /></label>
    </div></fieldset>
  </>;
}

export function NonconformitiesWorkspace({ onAccessDenied, preferredUnitId, onUnitChange }: { onAccessDenied?: () => void; preferredUnitId?: string; onUnitChange?: (unitId: string) => void }) {
  const [initialPreferredUnitId] = useState(preferredUnitId ?? "");
  const [units, setUnits] = useState<Unit[]>([]);
  const [unitId, setUnitId] = useState("");
  const [caps, setCaps] = useState<string[]>([]);
  const [rows, setRows] = useState<Nonconformity[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [query, setQuery] = useState({ q: "", state: "", source_type: "", severity: "", offset: 0 });
  const [loading, setLoading] = useState(true);
  const [recordBusy, setBusy] = useState(false);
  const [linksBusy, setLinksBusy] = useState(false);
  const busy = recordBusy || linksBusy;
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
  const mutationBusy = useRef(false);
  const denied = useRef(onAccessDenied);
  const canRead = caps.includes("ncr.read");
  const canManage = canRead && caps.includes("ncr.manage");
  const canReview = canRead && caps.includes("ncr.review");
  const canReadProcesses = caps.includes("processes.read");
  const selected = rows.find((row) => row.id === selectedId);

  useEffect(() => { denied.current = onAccessDenied; }, [onAccessDenied]);
  useEffect(() => {
    const controller = new AbortController();
    const scopeEpoch = epoch;
    const mutationEpoch = mutation;
    void read<Unit[]>("/organization/units?limit=100", controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      const active = data.filter((unit) => unit.status === "active");
      const nextUnit = active.find((unit) => unit.id === initialPreferredUnitId)?.id ?? active[0]?.id ?? "";
      setUnits(active); setUnitId(nextUnit);
      if (!active.length) setLoading(false);
    }).catch((cause) => { if (!controller.signal.aborted) { setError(errorMessage(cause)); setLoading(false); } });
    return () => { controller.abort(); ++scopeEpoch.current; ++mutationEpoch.current; };
  }, [initialPreferredUnitId]);

  const invalidate = useCallback(() => {
    ++epoch.current; ++mutation.current;
    setCaps([]); setRows([]); setSelectedId(""); setCreating(false); setEditing(false);
    setProcesses([]); setMembers([]); setMemberNames({}); setProcessNames({});
    setError(""); setNotice(""); setLoading(true); setTransitionTarget("");
    setProcessSearch(""); setMemberSearch(""); setProcessOffset(0); setMemberOffset(0);
  }, []);

  useEffect(() => {
    const revision = ++epoch.current;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      if (!unitId) { setLoading(false); return; }
      setLoading(true); setError("");
      void read<{ capabilities: string[] }>(`/qms-access/effective?unit_id=${encodeURIComponent(unitId)}`, controller.signal).then(async (access) => {
        if (revision !== epoch.current || controller.signal.aborted) return;
        setCaps(access.capabilities);
        if (!access.capabilities.includes("ncr.read")) {
          setRows([]); setSelectedId(""); setCreating(false); setEditing(false); return;
        }
        const params = new URLSearchParams({ unit_id: unitId, q: query.q, limit: "50", offset: String(query.offset) });
        for (const field of ["state", "source_type", "severity"] as const) if (query[field]) params.set(field, query[field]);
        const data = await read<Nonconformity[]>(`/nonconformities?${params}`, controller.signal);
        if (revision !== epoch.current || controller.signal.aborted) return;
        setRows(data); setSelectedId((current) => data.some((row) => row.id === current) ? current : data[0]?.id ?? "");
      }).catch((cause) => {
        if (revision !== epoch.current || controller.signal.aborted) return;
        setRows([]); setSelectedId(""); setError(errorMessage(cause));
        if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); setCreating(false); setEditing(false); denied.current?.(); }
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
        if (controller.signal.aborted) return;
        setProcesses(nextProcesses); setMembers(nextMembers);
        setMemberNames((current) => ({ ...current, ...Object.fromEntries(nextMembers.map((member) => [member.id, member.display_name])) }));
        setProcessNames((current) => ({ ...current, ...Object.fromEntries(nextProcesses.map((process) => [process.id, `${process.code} · ${process.name}`])) }));
      }).catch((cause) => { if (!controller.signal.aborted) { setProcesses([]); setMembers([]); setError(errorMessage(cause)); } })
        .finally(() => { if (!controller.signal.aborted) setReferenceBusy(false); });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, canManage, canReadProcesses, creating, editing, processSearch, memberSearch, processOffset, memberOffset]);

  const selectedProcessId = selected?.process_id;
  useEffect(() => {
    const controller = new AbortController();
    if (!canRead || !selectedProcessId) return () => controller.abort();
    void read<Member[]>("/organization/members?limit=100", controller.signal).then((data) => {
      if (!controller.signal.aborted) setMemberNames((current) => ({ ...current, ...Object.fromEntries(data.map((member) => [member.id, member.display_name])) }));
    }).catch(() => { /* The saved record remains readable when the directory is unavailable. */ });
    if (canReadProcesses) void read<Process>(`/processes/${selectedProcessId}`, controller.signal).then((process) => {
      if (!controller.signal.aborted) setProcessNames((current) => ({ ...current, [process.id]: `${process.code} · ${process.name}` }));
    }).catch(() => { /* A nonconformity read grant does not grant process read authority. */ });
    return () => controller.abort();
  }, [canRead, canReadProcesses, selectedProcessId]);

  async function save(path: string, method: "POST" | "PATCH", body: object) {
    if (mutationBusy.current) return;
    mutationBusy.current = true;
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
      const result = await response.json() as Nonconformity;
      if (revision !== epoch.current || attempt !== mutation.current) return;
      setCreating(false); setEditing(false); setSelectedId(result.id); setTransitionTarget("");
      setRows((current) => current.map((row) => row.id === result.id ? result : row));
      if (method === "POST" && path === "/nonconformities") {
        setSearch(result.code); setStateFilter(""); setSourceFilter(""); setSeverityFilter("");
        setQuery({ q: result.code, state: "", source_type: "", severity: "", offset: 0 });
      }
      setNotice("Saved. The record history has been updated."); setRefresh((current) => current + 1);
    } catch (cause) {
      if (revision !== epoch.current || attempt !== mutation.current) return;
      setError(errorMessage(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) {
        setCaps([]); setRows([]); setSelectedId(""); setCreating(false); setEditing(false); denied.current?.();
      }
    } finally {
      mutationBusy.current = false;
      if (attempt === mutation.current) setBusy(false);
    }
  }

  async function submitRecord(event: React.FormEvent<HTMLFormElement>, record?: Nonconformity) {
    event.preventDefault(); if (!canManage || busy || (!record && !canReadProcesses)) return;
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {};
    for (const field of ["name", "source_type", "severity", "description", "detected_date", "containment_action", "disposition_notes", "root_cause_summary", "closure_notes"]) body[field] = String(data.get(field) ?? "");
    for (const field of ["target_date", "owner_user_id", "containment_owner_user_id", "containment_date", "disposition"]) body[field] = data.get(field) || null;
    body.containment_required = data.get("containment_required") === "true";
    body.containment_completed = data.get("containment_completed") === "true";
    if (record) body.expected_version = record.row_version;
    else { body.code = data.get("code"); body.process_id = data.get("process_id"); body.unit_id = unitId; }
    await save(record ? `/nonconformities/${record.id}` : "/nonconformities", record ? "PATCH" : "POST", body);
  }

  function referenceSearch() {
    return <div className="ncr-reference-search">
      {creating && <div><label>Find a process<input maxLength={160} value={processSearch} onChange={(event) => { setProcessSearch(event.target.value); setProcessOffset(0); }} disabled={busy} /></label><nav aria-label="Nonconformity process search pages"><button type="button" disabled={busy || referenceBusy || processOffset === 0} onClick={() => setProcessOffset(Math.max(0, processOffset - 50))}>Previous processes</button><button type="button" disabled={busy || referenceBusy || processes.length < 50 || processOffset >= 1_000_000} onClick={() => setProcessOffset(processOffset + 50)}>More processes</button></nav></div>}
      <div><label>Find a responsible person<input maxLength={160} value={memberSearch} onChange={(event) => { setMemberSearch(event.target.value); setMemberOffset(0); }} disabled={busy} /></label><nav aria-label="Nonconformity member search pages"><button type="button" disabled={busy || referenceBusy || memberOffset === 0} onClick={() => setMemberOffset(Math.max(0, memberOffset - 50))}>Previous people</button><button type="button" disabled={busy || referenceBusy || members.length < 50 || memberOffset >= 1_000_000} onClick={() => setMemberOffset(memberOffset + 50)}>More people</button></nav></div>
    </div>;
  }

  const memberName = (id: string | null) => id ? memberNames[id] ?? "Recorded member" : "Unassigned";
  const availableTargets = selected ? (transitions[selected.state] ?? []).filter((target) => target === "open" ? canManage : canReview) : [];
  const blocked = (target: string) => !!selected && ((target === "containment" && !selected.containment_required)
    || (["investigation", "closed"].includes(target) && selected.containment_required && !selected.containment_completed));
  const effectiveTarget = availableTargets.includes(transitionTarget) && !blocked(transitionTarget) ? transitionTarget : availableTargets.find((target) => !blocked(target)) ?? "";

  return <section className="ncr-panel" aria-labelledby="ncr-heading" aria-busy={loading || busy}>
    <div className="workspace-heading"><div><p className="eyebrow">Quality response</p><h2 id="ncr-heading"><AlertTriangle size={22} aria-hidden="true" /> Nonconformities</h2><p className="workspace-subtitle">Contain issues, investigate causes and document the decision to close.</p></div><button className="secondary-action compact-action" type="button" disabled={loading || busy || !unitId} onClick={() => { setEditing(false); setCreating(false); setRefresh((value) => value + 1); }}><RefreshCw size={16} aria-hidden="true" /> Refresh nonconformities</button></div>
    <fieldset className="ncr-toolbar" disabled={busy}>
      <label>Organization scope<select value={unitId} onChange={(event) => {
        invalidate(); setUnitId(event.target.value); onUnitChange?.(event.target.value); setSearch(""); setStateFilter(""); setSourceFilter(""); setSeverityFilter("");
        setQuery({ q: "", state: "", source_type: "", severity: "", offset: 0 });
      }}><option value="">Select a unit</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.code} · {unit.name}</option>)}</select></label>
      {canRead && <form onSubmit={(event) => { event.preventDefault(); setEditing(false); setCreating(false); setQuery({ q: search.trim(), state: stateFilter, source_type: sourceFilter, severity: severityFilter, offset: 0 }); }}>
        <label>Find by code or title<input value={search} maxLength={160} onChange={(event) => setSearch(event.target.value)} /></label>
        <label>Status<select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}><option value="">All statuses</option>{states.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        <label>Source<select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}><option value="">All sources</option>{sources.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        <label>Severity<select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option value="">All severities</option>{severities.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        <button className="secondary-action compact-action" type="submit" disabled={loading}>Search records</button>
      </form>}
    </fieldset>
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {loading ? <RecordWorkspaceSkeleton label="Loading nonconformity access and records" /> : !unitId ? <p className="ncr-empty">Select an active organization unit.</p> : !canRead ? <p className="ncr-empty">No nonconformity read responsibility is assigned for this unit. Contact the organization owner.</p> : <>
      {canManage && <div className="ncr-create-action"><button className="primary-action compact-action" type="button" disabled={busy || !canReadProcesses} onClick={() => { setCreating((value) => !value); setEditing(false); }}><Plus size={16} aria-hidden="true" /> New nonconformity</button>{!canReadProcesses && <p className="qms-history-caption">Process read responsibility is needed to register a nonconformity against an active process.</p>}</div>}
      {creating && canManage && <form className="ncr-editor" onSubmit={(event) => void submitRecord(event)}><h3>Register a nonconformity</h3>{referenceSearch()}<fieldset className="ncr-editor-content" disabled={busy || referenceBusy}>
        <NCRFields members={members} memberNames={memberNames} processes={processes} />
        <div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Register</button><button className="secondary-action compact-action" type="button" onClick={() => setCreating(false)}>Cancel</button></div>
      </fieldset></form>}
      <div className="ncr-register-grid"><aside aria-label="Nonconformity register"><h3>Register <span>{rows.length}</span></h3>
        {rows.length ? <ul className="ncr-record-list">{rows.map((row) => <li key={row.id}><button type="button" disabled={busy} aria-pressed={row.id === selectedId} onClick={() => { setSelectedId(row.id); setEditing(false); setCreating(false); setTransitionTarget(""); setError(""); }}><span className="ncr-list-heading"><strong>{row.code}</strong><span className={`ncr-severity ${row.severity}`}>{label(row.severity)}</span></span><span>{row.name}</span><small>{label(row.state)} · {label(row.source_type)}</small>{row.is_overdue && <small className="ncr-overdue">{row.days_overdue} days overdue</small>}</button></li>)}</ul> : <p className="ncr-empty">No records match this scope and search.</p>}
        <nav className="ncr-pagination" aria-label="Nonconformity register pages"><button type="button" disabled={busy || query.offset === 0} onClick={() => { setEditing(false); setCreating(false); setQuery({ ...query, offset: Math.max(0, query.offset - 50) }); }}>Previous</button><span>Page {Math.floor(query.offset / 50) + 1}</span><button type="button" disabled={busy || rows.length < 50 || query.offset >= 1_000_000} onClick={() => { setEditing(false); setCreating(false); setQuery({ ...query, offset: query.offset + 50 }); }}>Next</button></nav>
      </aside><div>{selected ? <article className="ncr-detail" key={selected.id}>
        <div className="ncr-detail-heading"><div><p className="eyebrow">{selected.code} · {label(selected.source_type)}</p><h3>{selected.name}</h3></div><div className="ncr-badges"><span className="process-status">{label(selected.state)}</span><span className={`ncr-severity ${selected.severity}`}>{label(selected.severity)}</span></div></div>
        <p className="ncr-description">{selected.description}</p>
        {selected.is_overdue && <p className="ncr-overdue">Target date is {selected.days_overdue} days overdue.</p>}
        <dl className="ncr-metadata"><div><dt>Process</dt><dd>{processNames[selected.process_id] ?? "Linked process"}</dd></div><div><dt>Responsible person</dt><dd>{memberName(selected.owner_user_id)}</dd></div><div><dt>Detected</dt><dd>{dateLabel(selected.detected_date)}</dd></div><div><dt>Detected by</dt><dd>{memberName(selected.detected_by_user_id)}</dd></div><div><dt>Target</dt><dd>{dateLabel(selected.target_date)}</dd></div></dl>
        <section className="ncr-read-section"><h4>Containment</h4><p className={`ncr-containment-state ${selected.containment_required && !selected.containment_completed ? "pending" : ""}`}>{selected.containment_required ? (selected.containment_completed ? "Required containment completed" : "Required containment is pending") : (selected.containment_completed ? "Containment completed" : "Containment is not required")}</p><p>{selected.containment_action || "No containment action recorded."}</p><dl className="ncr-metadata"><div><dt>Responsible person</dt><dd>{memberName(selected.containment_owner_user_id)}</dd></div><div><dt>Completed on</dt><dd>{dateLabel(selected.containment_date)}</dd></div></dl></section>
        <section className="ncr-read-section"><h4>Investigation and disposition</h4><dl className="ncr-narratives"><div><dt>Root cause summary</dt><dd>{selected.root_cause_summary || "Not recorded"}</dd></div><div><dt>Disposition</dt><dd>{selected.disposition ? label(selected.disposition) : "Not decided"}</dd></div><div><dt>Disposition notes</dt><dd>{selected.disposition_notes || "Not recorded"}</dd></div><div><dt>Closure notes</dt><dd>{selected.closure_notes || "Not recorded"}</dd></div>{selected.cancellation_reason && <div><dt>Cancellation reason</dt><dd>{selected.cancellation_reason}</dd></div>}</dl></section>
        <details className="ncr-timeline"><summary>Opening, review and closure details</summary><dl className="ncr-metadata">{([
          ["Opened", selected.opened_at, selected.opened_by_user_id], ["Last reviewed", selected.reviewed_at, selected.reviewed_by_user_id],
          ["Closed", selected.closed_at, selected.closed_by_user_id], ["Cancelled", selected.cancelled_at, selected.cancelled_by_user_id],
        ] as const).map(([title, date, person]) => <div key={title}><dt>{title}</dt><dd>{dateLabel(date)}{person && <small>{memberName(person)}</small>}</dd></div>)}</dl></details>
        <RelatedCAPAs key={`capa-${selected.id}-${selected.unit_id}-${selected.process_id}`} origin={{ ...selected, kind: "ncr" }} capabilities={caps} disabled={busy || editing || creating}
          onBusyChange={(value) => { mutationBusy.current = value; setLinksBusy(value); }}
          onAccessChanged={() => { invalidate(); setRefresh((value) => value + 1); denied.current?.(); }} />
        <NCRLinks ncr={selected} capabilities={caps} disabled={busy || editing || creating}
          onVersionChange={(version) => setRows((current) => current.map((row) => row.id === selected.id ? { ...row, row_version: version } : row))}
          onBusyChange={(value) => { mutationBusy.current = value; setLinksBusy(value); }}
          onAccessChanged={() => { setCreating(false); setEditing(false); setRefresh((value) => value + 1); }}
          onRefresh={() => { setEditing(false); setRefresh((value) => value + 1); }} />
        {canManage && !terminal(selected.state) && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => setEditing((value) => !value)}>{editing ? "Cancel editing" : "Edit record"}</button>}
        {editing && canManage && !terminal(selected.state) && <form className="ncr-editor" onSubmit={(event) => void submitRecord(event, selected)}><h4>Edit {selected.code}</h4>{referenceSearch()}<fieldset className="ncr-editor-content" disabled={busy || referenceBusy}><NCRFields record={selected} members={members} memberNames={memberNames} processes={processes} /><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Save record</button></div></fieldset></form>}
        {!editing && !!availableTargets.length && !terminal(selected.state) && <form className="ncr-transition" onSubmit={(event) => {
          event.preventDefault(); if (busy || !effectiveTarget || blocked(effectiveTarget)) return;
          const data = new FormData(event.currentTarget);
          void save(`/nonconformities/${selected.id}/transition`, "POST", { expected_version: selected.row_version, target_state: effectiveTarget, decision: data.get("decision"), ...(effectiveTarget === "closed" ? { closure_notes: data.get("closure_notes") } : {}) });
        }}><h4>Review and workflow</h4><fieldset disabled={busy}><label>Action<select value={effectiveTarget} onChange={(event) => setTransitionTarget(event.target.value)}>{!effectiveTarget && <option value="">Complete the required containment first</option>}{availableTargets.map((target) => <option key={target} value={target} disabled={blocked(target)}>{target === "open" ? "Open nonconformity" : target === "cancelled" ? "Cancel nonconformity" : `Move to ${label(target)}`}</option>)}</select></label>
          {selected.containment_required && !selected.containment_completed && <p className="qms-history-caption">Complete the required containment before investigation or closure.</p>}
          <label>{effectiveTarget === "cancelled" ? "Cancellation reason" : "Decision"}<textarea name="decision" required maxLength={500} rows={2} /></label>
          {effectiveTarget === "closed" && <label>Closure notes<textarea name="closure_notes" required maxLength={4000} rows={3} defaultValue={selected.closure_notes} /></label>}
          <button className="secondary-action compact-action" type="submit" disabled={!effectiveTarget}>Record decision</button>
        </fieldset></form>}
        {!editing && !availableTargets.length && !terminal(selected.state) && <p className="qms-history-caption">A review responsibility is needed to advance this record.</p>}
        {terminal(selected.state) && <p className="qms-history-caption">This {selected.state} record is preserved for traceability.</p>}
      </article> : <div className="ncr-empty"><strong>Select a record</strong><p>Review its detection, containment and current response.</p></div>}</div></div>
    </>}
  </section>;
}
