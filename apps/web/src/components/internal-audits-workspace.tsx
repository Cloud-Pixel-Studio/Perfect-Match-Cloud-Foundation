"use client";

import { CalendarDays, ClipboardList, Plus, RefreshCw } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useId, useRef, useState } from "react";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Unit = { id: string; code: string; name: string; status: string };
type Member = { id: string; display_name: string };
type BaseRecord = {
  id: string; unit_id: string; code: string; name: string; objective: string;
  state: string; row_version: number; cancellation_reason: string;
  created_at: string; updated_at: string; completed_at: string | null; cancelled_at: string | null;
};
type Program = BaseRecord & {
  date_start: string; date_end: string; description: string;
  owner_user_id: string | null; approved_at: string | null;
};
type InternalAudit = BaseRecord & {
  program_id: string | null; audit_type: string; planned_start: string; planned_end: string;
  scope_summary: string; conclusion: string; lead_auditor_user_id: string | null;
  independence_status: string; independence_notes: string; independence_reviewed_at: string | null;
};
type PlanningRecord = Program | InternalAudit;
type Kind = "programs" | "audits";
type Editor = { kind: Kind; record: PlanningRecord | null };
type Command = { kind: Kind; record: PlanningRecord; target: string; action: string };
const api = "/api/identity";
const root = "/internal-audits/";
const pageSize = 20;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const dates = /^\d{4}-\d{2}-\d{2}$/;
const types = ["system", "process", "department", "special", "follow_up"];
const actions: Record<string, string> = {
  approved: "Approve program", active: "Activate program", completed: "Complete program", planned: "Mark as planned",
};
const programTransitions: Record<string, string[]> = {
  draft: ["approved", "cancelled"], approved: ["active", "cancelled"], active: ["completed", "cancelled"],
};
const pretty = (value: string) => value.replaceAll("_", " ");
const isProgram = (row: PlanningRecord): row is Program => "date_start" in row;
const terminal = (row: PlanningRecord) => row.state === "completed" || row.state === "cancelled";
const editable = (row: PlanningRecord) => !terminal(row) && (isProgram(row) || ["draft", "planned"].includes(row.state));
const dateLabel = (value: string | null) => value && dates.test(value)
  ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(value)) : "Not recorded";
const timestamp = (value: string | null) => value
  ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not recorded";
class ResponseError extends Error {
  constructor(readonly status: number) { super(String(status)); }
}
function message(cause: unknown) {
  const status = cause instanceof ResponseError ? cause.status : 0;
  if (status === 401) return "Your session has expired. Sign in again.";
  if (status === 403) return "Your audit responsibilities changed. Refresh your access before continuing.";
  if (status === 404) return "This audit record or scope is unavailable with your current access. Refresh the workspace.";
  if (status === 409) return "The record, program, member or version conflicts with the current state. Review the draft and refresh before trying again. A cancelled program must be replaced or removed from the audit.";
  if (status === 422) return "Review the required fields and date range before saving.";
  return cause instanceof Error && !(cause instanceof ResponseError) && cause.message.startsWith("The ")
    ? cause.message : "Audit planning is temporarily unavailable. Try refreshing.";
}
const lostAccess = (cause: unknown) => cause instanceof ResponseError && [401, 403, 404].includes(cause.status);
async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(api + path, { credentials: "include", signal });
  if (response.status !== 200) throw new ResponseError(response.status);
  return await response.json() as T;
}
function validRecord(row: PlanningRecord, kind: Kind, unitId: string) {
  return row !== null && typeof row === "object" && typeof row.id === "string" && uuid.test(row.id)
    && row.unit_id === unitId && typeof row.code === "string" && typeof row.name === "string"
    && typeof row.objective === "string" && typeof row.state === "string"
    && Number.isInteger(row.row_version) && row.row_version > 0
    && (kind === "programs" ? isProgram(row) && dates.test(row.date_start) && dates.test(row.date_end)
      : !isProgram(row) && dates.test(row.planned_start) && dates.test(row.planned_end));
}
function csrfToken() {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

function ReferencePicker({ kind, name, title, unitId, initialId, initialLabel, disabled, onAccessError }: {
  kind: "members" | "programs"; name: string; title: string; unitId: string;
  initialId?: string | null; initialLabel?: string; disabled: boolean; onAccessError: (cause: unknown) => void;
}) {
  const [value, setValue] = useState(initialId ?? "");
  const [pinnedLabel, setPinnedLabel] = useState(initialLabel ?? (kind === "members" ? "Assigned member outside this page" : "Linked program outside this page"));
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState({ search: "", offset: 0, refresh: 0 });
  const [options, setOptions] = useState<Array<{ id: string; label: string }>>([]);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const epoch = useRef(0);
  const chosen = useRef(initialId ?? "");
  const access = useRef(onAccessError);
  useEffect(() => { access.current = onAccessError; }, [onAccessError]);
  useEffect(() => {
    const controller = new AbortController();
    const generation = ++epoch.current;
    const current = () => !controller.signal.aborted && generation === epoch.current;
    const timer = window.setTimeout(() => {
      setLoading(true); setError(""); setOptions([]); setHasNext(false);
      const params = new URLSearchParams({ limit: "21", offset: String(query.offset) });
      params.set(kind === "members" ? "search" : "q", query.search);
      if (kind === "programs") params.set("unit_id", unitId);
      void read<Array<Member | Program>>((kind === "members" ? "/organization/members?" : root + "programs?") + params, controller.signal).then((data) => {
        if (!current()) return;
        if (!Array.isArray(data) || data.some((row) => !row || typeof row.id !== "string" || !uuid.test(row.id)
          || (kind === "programs" && (!("unit_id" in row) || row.unit_id !== unitId)))) throw new Error("The directory response could not be verified. Refresh its choices.");
        const next = data.slice(0, pageSize).filter((row) => kind === "members" || ("state" in row && row.state !== "cancelled"))
          .map((row) => ({ id: row.id, label: "display_name" in row ? row.display_name : row.code + " · " + row.name + " · " + pretty(row.state) }));
        setOptions(next); setHasNext(data.length > pageSize);
        const selected = next.find((row) => row.id === chosen.current);
        if (selected) setPinnedLabel(selected.label);
      }).catch((cause) => { if (current()) { setError(message(cause)); if (lostAccess(cause)) access.current(cause); } })
        .finally(() => { if (current()) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [kind, unitId, query]);
  return <div className="ia-reference-picker">
    <div className="ia-reference-toolbar"><label>{kind === "programs" ? "Find program" : name === "owner_user_id" ? "Find responsible person" : "Find lead auditor"}<input value={search} maxLength={160} disabled={disabled} onChange={(event) => setSearch(event.target.value)} /></label>
      <button type="button" className="secondary-action compact-action" disabled={disabled || loading} onClick={() => setQuery({ search: search.trim(), offset: 0, refresh: query.refresh + 1 })}>{kind === "programs" ? "Search programs" : "Search people"}</button></div>
    <input type="hidden" name={name} value={value} />
    <label>{title}<select aria-label={title} value={value} disabled={disabled || loading} onChange={(event) => {
      chosen.current = event.target.value; setValue(event.target.value);
      const option = options.find((row) => row.id === event.target.value); if (option) setPinnedLabel(option.label);
    }}><option value="">{kind === "programs" ? "No program" : "Unassigned"}</option>
      {value && !options.some((row) => row.id === value) && <option value={value}>{pinnedLabel}</option>}
      {options.map((row) => <option key={row.id} value={row.id}>{row.label}</option>)}</select></label>
    {loading && <p className="qms-history-caption" role="status">Loading {kind === "programs" ? "program" : "member"} choices…</p>}
    {error && <p role="alert" className="denied-state">{error} <button type="button" className="secondary-action compact-action" disabled={disabled} onClick={() => setQuery({ ...query, refresh: query.refresh + 1 })}>Retry choices</button></p>}
    {!loading && !error && !options.length && <p className="qms-history-caption">No selectable {kind === "programs" ? "programs" : "members"} on this page. Change the search or page.</p>}
    <nav className="ia-reference-pages" aria-label={kind === "programs" ? "Program choices pages" : "Member choices pages"}>
      <button type="button" className="secondary-action compact-action" disabled={disabled || loading || query.offset === 0} onClick={() => setQuery({ ...query, offset: Math.max(0, query.offset - pageSize) })}>Previous choices</button><span>Page {Math.floor(query.offset / pageSize) + 1}</span>
      <button type="button" className="secondary-action compact-action" disabled={disabled || loading || !hasNext || query.offset + pageSize > (kind === "members" ? 10000 : 1_000_000)} onClick={() => setQuery({ ...query, offset: query.offset + pageSize })}>More choices</button></nav>
  </div>;
}

function PlanningScope({ unit, capabilities, onAccessError, onBusyChange }: {
  unit: Unit; capabilities: string[]; onAccessError: (cause: unknown) => void; onBusyChange: (busy: boolean) => void;
}) {
  const canManage = capabilities.includes("audits.read") && capabilities.includes("audits.manage");
  const canReview = capabilities.includes("audits.read") && capabilities.includes("audits.review");
  const [kind, setKind] = useState<Kind>("programs");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState({ q: "", offset: 0 });
  const [refresh, setRefresh] = useState(0);
  const [records, setRecords] = useState<PlanningRecord[]>([]);
  const [selected, setSelected] = useState<PlanningRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasNext, setHasNext] = useState(false);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [command, setCommand] = useState<Command | null>(null);
  const [busy, setBusy] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [memberNames, setMemberNames] = useState<Record<string, string>>({});
  const [programNames, setProgramNames] = useState<Record<string, string>>({});
  const requestEpoch = useRef(0);
  const mutationEpoch = useRef(0);
  const pending = useRef(false);
  const access = useRef(onAccessError);
  const busyCallback = useRef(onBusyChange);
  const tabId = useId();
  useEffect(() => { access.current = onAccessError; busyCallback.current = onBusyChange; }, [onAccessError, onBusyChange]);
  const invalidate = useCallback((cause: unknown) => {
    ++requestEpoch.current; ++mutationEpoch.current; pending.current = false; busyCallback.current(false);
    setRecords([]); setSelected(null); setEditor(null); setCommand(null); setMemberNames({}); setProgramNames({});
    setNotice(""); setError(""); setBusy(false); setLoading(false); access.current(cause);
  }, []);
  useEffect(() => {
    const requests = requestEpoch; const mutations = mutationEpoch; const pendingWrite = pending; const notifyBusy = busyCallback;
    return () => { ++requests.current; ++mutations.current; if (pendingWrite.current) notifyBusy.current(false); };
  }, []);
  useEffect(() => {
    const controller = new AbortController(); const generation = ++requestEpoch.current;
    const current = () => !controller.signal.aborted && generation === requestEpoch.current;
    const timer = window.setTimeout(() => {
      setLoading(true); setRecords([]); setHasNext(false);
      const params = new URLSearchParams({ unit_id: unit.id, limit: "21", offset: String(query.offset) });
      if (kind === "programs") params.set("q", query.q);
      void read<PlanningRecord[]>(root + kind + "?" + params, controller.signal).then((data) => {
        if (!current()) return;
        if (!Array.isArray(data) || data.some((row) => !validRecord(row, kind, unit.id))) throw new Error("The audit register response did not match this scope. Refresh the workspace.");
        const next = data.slice(0, pageSize); setRecords(next); setHasNext(data.length > pageSize);
        setSelected((current) => current ? next.find((row) => row.id === current.id) ?? current : next[0] ?? null);
        if (kind === "programs") setProgramNames((current) => ({ ...current, ...Object.fromEntries(next.map((row) => [row.id, row.code + " · " + row.name])) }));
      }).catch((cause) => { if (current()) { setSelected(null); setError(message(cause)); if (lostAccess(cause)) invalidate(cause); } })
        .finally(() => { if (current()) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unit.id, kind, query, refresh, invalidate]);
  useEffect(() => {
    const controller = new AbortController();
    void read<Member[]>("/organization/members?limit=100", controller.signal).then((data) => {
      if (!controller.signal.aborted && Array.isArray(data)) setMemberNames(Object.fromEntries(data.map((row) => [row.id, row.display_name])));
    }).catch((cause) => { if (!controller.signal.aborted && lostAccess(cause)) invalidate(cause); });
    return () => controller.abort();
  }, [invalidate]);
  const linkedProgram = selected && !isProgram(selected) ? selected.program_id : null;
  useEffect(() => {
    if (!linkedProgram) return;
    const controller = new AbortController();
    void read<Program>(root + "programs/" + linkedProgram, controller.signal).then((row) => {
      if (controller.signal.aborted) return;
      if (!validRecord(row, "programs", unit.id) || row.id !== linkedProgram) throw new Error("The linked program could not be verified.");
      setProgramNames((current) => ({ ...current, [row.id]: row.code + " · " + row.name + (row.state === "cancelled" ? " (cancelled)" : "") }));
    }).catch((cause) => { if (!controller.signal.aborted && lostAccess(cause)) invalidate(cause); });
    return () => controller.abort();
  }, [linkedProgram, unit.id, invalidate]);
  function changeKind(next: Kind) {
    if (pending.current) return;
    ++requestEpoch.current; setKind(next); setRecords([]); setSelected(null); setEditor(null); setCommand(null);
    setSearch(""); setQuery({ q: "", offset: 0 }); setError(""); setNotice("");
  }
  function select(row: PlanningRecord) {
    if (pending.current) return;
    setSelected(row); setEditor(null); setCommand(null); setError(""); setNotice("");
  }
  async function write(path: string, method: "POST" | "PATCH", body: Record<string, unknown>, recordKind: Kind, expectedId: string | null, success: string) {
    if (pending.current || unconfirmed || conflict) return;
    pending.current = true; setBusy(true); busyCallback.current(true); setError(""); setNotice("");
    const token = ++mutationEpoch.current; const generation = requestEpoch.current;
    const current = () => token === mutationEpoch.current && generation === requestEpoch.current;
    let responseReceived = false;
    try {
      const response = await fetch(api + path, { method, credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() }, body: JSON.stringify(body) });
      responseReceived = true; if (!current()) return;
      if (!response.ok) {
        const cause = new ResponseError(response.status); if (lostAccess(cause)) { invalidate(cause); return; }
        if (response.status === 409) setConflict(true); throw cause;
      }
      setUnconfirmed(true);
      if (response.status !== (expectedId ? 200 : 201)) throw new Error("The command outcome could not be confirmed. Refresh the workspace and review the record before another submission.");
      const row = await response.json() as PlanningRecord; if (!current()) return;
      const expectedVersion = expectedId ? Number(body.expected_version) + 1 : 1;
      if (!validRecord(row, recordKind, unit.id) || row.row_version !== expectedVersion || (expectedId ? row.id !== expectedId : row.code !== body.code || row.state !== "draft")
        || (body.target_state && row.state !== body.target_state)) throw new Error("The command response could not be verified. Refresh the workspace before another submission.");
      setUnconfirmed(false); setSelected(row); setEditor(null); setCommand(null); setNotice(success + " " + row.code + "."); setRefresh((value) => value + 1);
    } catch (cause) {
      if (!current()) return;
      if (!responseReceived) setUnconfirmed(true); setError(message(cause));
    } finally {
      if (current()) { pending.current = false; setBusy(false); busyCallback.current(false); }
    }
  }
  function save(event: FormEvent<HTMLFormElement>, target: Editor) {
    event.preventDefault(); if (!canManage || pending.current || unconfirmed || conflict) return;
    const data = new FormData(event.currentTarget); const name = String(data.get("name") ?? "").trim();
    const objective = String(data.get("objective") ?? "").trim(); const code = String(data.get("code") ?? "").trim();
    const from = String(data.get(target.kind === "programs" ? "date_start" : "planned_start") ?? "");
    const to = String(data.get(target.kind === "programs" ? "date_end" : "planned_end") ?? "");
    if (!name || (!target.record && !code) || (target.kind === "audits" && !objective) || !from || !to || to < from) { setError("Review the title, code, objective and date range before saving."); return; }
    const body: Record<string, unknown> = { name, objective };
    if (target.record) body.expected_version = target.record.row_version; else { body.unit_id = unit.id; body.code = code; }
    if (target.kind === "programs") Object.assign(body, { date_start: from, date_end: to, description: String(data.get("description") ?? ""), owner_user_id: data.get("owner_user_id") || null });
    else Object.assign(body, { planned_start: from, planned_end: to, audit_type: data.get("audit_type"), scope_summary: String(data.get("scope_summary") ?? ""), program_id: data.get("program_id") || null, lead_auditor_user_id: data.get("lead_auditor_user_id") || null });
    void write(root + target.kind + (target.record ? "/" + target.record.id : ""), target.record ? "PATCH" : "POST", body, target.kind, target.record?.id ?? null, target.record ? "Saved" : "Created");
  }
  const locked = busy || unconfirmed || conflict;
  const ownerLabel = (id: string | null) => id ? memberNames[id] ?? "Assigned tenant member" : "Unassigned";
  const selectedOutsidePage = !!selected && !records.some((row) => row.id === selected.id);
  const title = kind === "programs" ? "Programs" : "Scheduled audits";
  return <>
    <div className="ia-tabs" role="tablist" aria-label="Audit planning registers" onKeyDown={(event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key) || busy) return;
      event.preventDefault(); const next: Kind = event.key === "Home" ? "programs" : event.key === "End" ? "audits" : kind === "programs" ? "audits" : "programs";
      changeKind(next); document.getElementById(tabId + "-" + next)?.focus();
    }}>
      <button type="button" role="tab" id={tabId + "-programs"} tabIndex={kind === "programs" ? 0 : -1} aria-controls={tabId + "-panel"} aria-selected={kind === "programs"} disabled={busy} onClick={() => changeKind("programs")}>Programs</button>
      <button type="button" role="tab" id={tabId + "-audits"} tabIndex={kind === "audits" ? 0 : -1} aria-controls={tabId + "-panel"} aria-selected={kind === "audits"} disabled={busy} onClick={() => changeKind("audits")}>Scheduled audits</button></div>
    <div role="tabpanel" id={tabId + "-panel"} aria-labelledby={tabId + "-" + kind} tabIndex={0}>
      <div className="ia-toolbar">
        {kind === "programs" ? <form aria-label="Search audit programs" onSubmit={(event) => {
          event.preventDefault(); if (pending.current) return; setSelected(null); setEditor(null); setCommand(null); setError(""); setQuery({ q: search.trim(), offset: 0 });
        }}><label>Find a program by code or title<input maxLength={160} value={search} disabled={busy} onChange={(event) => setSearch(event.target.value)} /></label><button type="submit" className="secondary-action compact-action" disabled={busy || loading}>Search programs</button></form>
          : <p className="qms-history-caption">Audits are ordered by planned start date. This register shows one page in the current organization scope.</p>}
        {canManage && <button type="button" className="primary-action compact-action" disabled={locked || loading} onClick={() => { setEditor({ kind, record: null }); setCommand(null); setError(""); setNotice(""); }}><Plus size={16} aria-hidden="true" />{kind === "programs" ? "New program" : "New audit"}</button>}</div>
      {error && <p role="alert" className="denied-state">{error}</p>}{notice && <p role="status" className="workflow-message">{notice}</p>}
      {unconfirmed && <p role="status" className="ia-planning-note">The command outcome is unconfirmed. Refresh the planning workspace and review the current record before another submission. The draft cannot be resubmitted.</p>}
      {conflict && <p role="status" className="ia-planning-note">The draft is preserved. Refresh the planning workspace to read the latest version and review the program or member before submitting again.</p>}
      {editor && canManage && <form key={editor.kind + "-" + (editor.record?.id ?? "new") + "-" + (editor.record?.row_version ?? 0)} className="ncr-editor" aria-label={(editor.record ? "Edit " : "Create ") + (editor.kind === "programs" ? "audit program" : "internal audit")} onSubmit={(event) => save(event, editor)}>
        <h3>{editor.record ? "Edit " + editor.record.code : editor.kind === "programs" ? "Create audit program" : "Create internal audit"}</h3>
        {editor.record && <p className="qms-history-caption">Version {editor.record.row_version} · The record code and organization scope remain fixed.</p>}
        <fieldset className="ncr-editor-content" disabled={busy}><div className="ncr-form-grid">
          {!editor.record && <label>Code<input name="code" maxLength={40} required /></label>}
          <label className={editor.record ? "ncr-wide" : undefined}>Title<input name="name" maxLength={160} defaultValue={editor.record?.name ?? ""} required /></label>
          <label className="ncr-wide">Objective<textarea name="objective" maxLength={4000} rows={3} defaultValue={editor.record?.objective ?? ""} required={editor.kind === "audits"} /></label>
          {editor.kind === "programs" ? <>
            <label>Starts on<input type="date" name="date_start" required defaultValue={editor.record && isProgram(editor.record) ? editor.record.date_start : ""} /></label>
            <label>Ends on<input type="date" name="date_end" required defaultValue={editor.record && isProgram(editor.record) ? editor.record.date_end : ""} /></label>
            <label className="ncr-wide">Description<textarea name="description" maxLength={4000} rows={3} defaultValue={editor.record && isProgram(editor.record) ? editor.record.description : ""} /></label>
            <div className="ncr-wide"><ReferencePicker kind="members" name="owner_user_id" title="Responsible person (optional)" unitId={unit.id} initialId={editor.record && isProgram(editor.record) ? editor.record.owner_user_id : null} initialLabel={editor.record && isProgram(editor.record) ? ownerLabel(editor.record.owner_user_id) : undefined} disabled={busy} onAccessError={invalidate} /></div>
          </> : <>
            <label>Audit type<select aria-label="Audit type" name="audit_type" defaultValue={editor.record && !isProgram(editor.record) ? editor.record.audit_type : "process"}>{types.map((type) => <option key={type} value={type}>{pretty(type)}</option>)}</select></label>
            <label>Planned start<input type="date" name="planned_start" required defaultValue={editor.record && !isProgram(editor.record) ? editor.record.planned_start : ""} /></label>
            <label>Planned end<input type="date" name="planned_end" required defaultValue={editor.record && !isProgram(editor.record) ? editor.record.planned_end : ""} /></label>
            <label className="ncr-wide">Scope summary<textarea name="scope_summary" maxLength={4000} rows={3} defaultValue={editor.record && !isProgram(editor.record) ? editor.record.scope_summary : ""} /></label>
            <div className="ncr-wide"><ReferencePicker kind="programs" name="program_id" title="Program (optional)" unitId={unit.id} initialId={editor.record && !isProgram(editor.record) ? editor.record.program_id : null} initialLabel={editor.record && !isProgram(editor.record) && editor.record.program_id ? programNames[editor.record.program_id] : undefined} disabled={busy} onAccessError={invalidate} /></div>
            <div className="ncr-wide"><ReferencePicker kind="members" name="lead_auditor_user_id" title="Lead auditor (optional)" unitId={unit.id} initialId={editor.record && !isProgram(editor.record) ? editor.record.lead_auditor_user_id : null} initialLabel={editor.record && !isProgram(editor.record) ? ownerLabel(editor.record.lead_auditor_user_id) : undefined} disabled={busy} onAccessError={invalidate} /></div>
            <p className="qms-history-caption ncr-wide">Assigning a lead auditor does not confirm independence or grant audit permissions. This workspace records planning only.</p>
          </>}</div><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={locked}>{busy ? "Saving…" : editor.record ? "Save planning details" : editor.kind === "programs" ? "Create program" : "Create audit"}</button><button type="button" className="secondary-action compact-action" onClick={() => setEditor(null)}>Cancel editing</button></div></fieldset></form>}
      {loading ? <RecordWorkspaceSkeleton label={"Loading " + title.toLowerCase()} /> : <div className="ncr-register-grid">
        <aside aria-label={title + " register"}><h3>{title}<span>{records.length} on this page</span></h3>
          {records.length ? <ul className="ncr-record-list">{records.map((row) => <li key={row.id}><button type="button" aria-pressed={row.id === selected?.id} disabled={busy} onClick={() => select(row)}><span className="ncr-list-heading"><strong>{row.code}</strong><span className="ia-record-status">{pretty(row.state)}</span></span><span>{row.name}</span><small>{dateLabel(isProgram(row) ? row.date_start : row.planned_start)} – {dateLabel(isProgram(row) ? row.date_end : row.planned_end)}</small></button></li>)}</ul>
            : <p className="ncr-empty">{kind === "programs" ? "No programs match this scope, search and page." : "No audits are scheduled on this page in the current scope."}</p>}
          <nav className="ncr-pagination" aria-label="Audit register pages"><button type="button" disabled={busy || query.offset === 0} onClick={() => { setSelected(null); setEditor(null); setCommand(null); setQuery({ ...query, offset: Math.max(0, query.offset - pageSize) }); }}>Previous</button><span>Page {Math.floor(query.offset / pageSize) + 1}</span><button type="button" disabled={busy || !hasNext || query.offset + pageSize > 1_000_000} onClick={() => { setSelected(null); setEditor(null); setCommand(null); setQuery({ ...query, offset: query.offset + pageSize }); }}>Next</button></nav></aside>
        {selected ? <article className="ncr-detail"><div className="ncr-detail-heading"><div><p className="eyebrow">{selected.code} · {isProgram(selected) ? "Audit program" : pretty(selected.audit_type) + " audit"}</p><h3>{selected.name}</h3></div><span className="process-status">{pretty(selected.state)}</span></div>
          {selectedOutsidePage && <p className="ia-selection-note">The saved record remains selected. It is outside the current register page or search.</p>}
          <p className="ia-scope-summary">{selected.objective || "No program objective recorded."}</p>
          <dl className="ncr-metadata"><div><dt>{isProgram(selected) ? "Starts" : "Planned start"}</dt><dd>{dateLabel(isProgram(selected) ? selected.date_start : selected.planned_start)}</dd></div><div><dt>{isProgram(selected) ? "Ends" : "Planned end"}</dt><dd>{dateLabel(isProgram(selected) ? selected.date_end : selected.planned_end)}</dd></div><div><dt>{isProgram(selected) ? "Responsible person" : "Lead auditor"}</dt><dd>{ownerLabel(isProgram(selected) ? selected.owner_user_id : selected.lead_auditor_user_id)}</dd></div><div><dt>Version</dt><dd>{selected.row_version}</dd></div>
            {!isProgram(selected) && <div className="ncr-wide"><dt>Program</dt><dd>{selected.program_id ? programNames[selected.program_id] ?? "Linked program" : "Standalone audit"}</dd></div>}</dl>
          {isProgram(selected) ? <section className="ncr-read-section"><h4>Program description</h4><p>{selected.description || "No additional description recorded."}</p></section> : <>
            <section className="ncr-read-section"><h4>Scope summary</h4><p>{selected.scope_summary || "No scope summary recorded."}</p></section>
            <section className="ncr-read-section"><h4>Independence review</h4><p>{pretty(selected.independence_status)}{selected.independence_reviewed_at ? " · " + timestamp(selected.independence_reviewed_at) : ""}</p>{selected.independence_notes && <p>{selected.independence_notes}</p>}<p className="qms-history-caption">Structured scope, criteria, team and independence decisions belong to the next audit stage. A planned record is not ready for execution.</p></section>
            {selected.conclusion && <section className="ncr-read-section"><h4>Recorded conclusion</h4><p>{selected.conclusion}</p></section>}</>}
          <details className="ncr-timeline"><summary>Record history</summary><dl className="ncr-metadata"><div><dt>Created</dt><dd>{timestamp(selected.created_at)}</dd></div><div><dt>Updated</dt><dd>{timestamp(selected.updated_at)}</dd></div>{isProgram(selected) && <div><dt>Approved</dt><dd>{timestamp(selected.approved_at)}</dd></div>}<div><dt>Completed</dt><dd>{timestamp(selected.completed_at)}</dd></div><div><dt>Cancelled</dt><dd>{timestamp(selected.cancelled_at)}</dd></div></dl></details>
          {selected.cancellation_reason && <p className="ia-planning-note">Cancellation reason: {selected.cancellation_reason}</p>}
          {!editor && !command && canManage && editable(selected) && <button type="button" className="secondary-action compact-action" disabled={locked} onClick={() => { setEditor({ kind, record: selected }); setError(""); setNotice(""); }}>Edit planning details</button>}
          {!editor && !command && <div className="ncr-form-actions">{(isProgram(selected) ? canReview ? programTransitions[selected.state] ?? [] : []
            : [...(selected.state === "draft" && canManage ? ["planned"] : []), ...(["draft", "planned"].includes(selected.state) && canReview ? ["cancelled"] : [])]).map((target) => {
            const action = target === "cancelled" ? isProgram(selected) ? "Cancel program" : "Cancel audit" : actions[target];
            return <button type="button" className="secondary-action compact-action" key={target} disabled={locked} onClick={() => { setCommand({ kind, record: selected, target, action }); setEditor(null); setError(""); setNotice(""); }}>{action}</button>;
          })}</div>}
          {command && <form className="ncr-transition ia-command-panel" aria-label={command.action + " " + command.record.code} onSubmit={(event) => {
            event.preventDefault(); if (pending.current || locked) return;
            const decision = String(new FormData(event.currentTarget).get("decision") ?? "").trim();
            if (!decision) { setError("Record a decision before confirming."); return; }
            void write(root + command.kind + "/" + command.record.id + "/transition", "POST", { expected_version: command.record.row_version, target_state: command.target, decision }, command.kind, command.record.id, "Recorded decision for");
          }}><h4>{command.action}: {command.record.code}</h4><p className="qms-history-caption">{command.record.name} · Version {command.record.row_version} · Current state: {pretty(command.record.state)}</p>
            {command.target === "cancelled" && <p className="ia-planning-note">Cancellation preserves this record and its history. Linked audits are not cancelled automatically.</p>}
            <fieldset disabled={busy}><label>{command.target === "cancelled" ? "Cancellation reason" : "Decision"}<textarea name="decision" maxLength={500} rows={3} required /></label><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={locked}>Confirm {command.action.toLowerCase()}</button><button type="button" className="secondary-action compact-action" onClick={() => setCommand(null)}>Keep current state</button></div></fieldset></form>}
          {terminal(selected) && <p className="qms-history-caption">This {pretty(selected.state)} record is preserved and cannot be edited.</p>}
          {!isProgram(selected) && !["draft", "planned", "cancelled"].includes(selected.state) && <p className="qms-history-caption">This audit is beyond the planning stage. Its execution commands are not available in this workspace.</p>}
        </article> : <div className="ncr-empty"><strong>{kind === "programs" ? "Select a program" : "Select a scheduled audit"}</strong><p>{canManage ? "Create a planning record or choose an existing entry to review its dates and responsibilities." : "Choose an entry to review its planning details."}</p></div>}</div>}
    </div>
  </>;
}

export function InternalAuditsWorkspace({ preferredUnitId, onUnitChange, onAccessDenied }: {
  preferredUnitId?: string; onUnitChange?: (unitId: string) => void; onAccessDenied?: () => void;
}) {
  const [initialPreferred] = useState(preferredUnitId ?? "");
  const [units, setUnits] = useState<Unit[]>([]); const [unitId, setUnitId] = useState("");
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0); const [blocked, setBlocked] = useState(false); const [error, setError] = useState("");
  const unitsEpoch = useRef(0); const scopeEpoch = useRef(0); const selectedUnit = useRef("");
  const denied = useRef(onAccessDenied); const scopeChange = useRef(onUnitChange);
  useEffect(() => { denied.current = onAccessDenied; scopeChange.current = onUnitChange; }, [onAccessDenied, onUnitChange]);
  useEffect(() => {
    const requests = unitsEpoch; const scope = scopeEpoch;
    return () => { ++requests.current; ++scope.current; };
  }, []);
  useEffect(() => {
    const controller = new AbortController(); const generation = ++unitsEpoch.current;
    const timer = window.setTimeout(() => {
      setLoading(true);
      void read<Unit[]>("/organization/units?limit=100", controller.signal).then((data) => {
        if (controller.signal.aborted || generation !== unitsEpoch.current) return;
        if (!Array.isArray(data) || data.some((row) => !row || typeof row.id !== "string" || !uuid.test(row.id))) throw new Error("The organization scopes could not be verified.");
        const active = data.filter((row) => row.status === "active"); setUnits(active);
        const next = active.find((row) => row.id === (selectedUnit.current || initialPreferred))?.id ?? active[0]?.id ?? "";
        selectedUnit.current = next; setUnitId(next); scopeChange.current?.(next); if (!next) setLoading(false);
      }).catch((cause) => {
        if (controller.signal.aborted || generation !== unitsEpoch.current) return;
        setUnits([]); setUnitId(""); setCapabilities([]); setError(message(cause)); setLoading(false); if (lostAccess(cause)) denied.current?.();
      });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [initialPreferred, refresh]);
  useEffect(() => {
    if (!unitId) return;
    const controller = new AbortController(); const generation = ++scopeEpoch.current;
    const timer = window.setTimeout(() => {
      setLoading(true); setCapabilities([]);
      void read<{ capabilities: string[] }>("/qms-access/effective?unit_id=" + encodeURIComponent(unitId), controller.signal).then((data) => {
        if (controller.signal.aborted || generation !== scopeEpoch.current) return;
        if (!Array.isArray(data.capabilities) || data.capabilities.some((value) => typeof value !== "string")) throw new Error("The audit responsibilities could not be verified.");
        setCapabilities(data.capabilities);
      }).catch((cause) => {
        if (controller.signal.aborted || generation !== scopeEpoch.current) return;
        setCapabilities([]); setError(message(cause)); setBlocked(true); if (lostAccess(cause)) denied.current?.();
      }).finally(() => { if (!controller.signal.aborted && generation === scopeEpoch.current) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, refresh]);
  const invalidate = useCallback((cause: unknown) => {
    ++scopeEpoch.current; setCapabilities([]); setBlocked(true); setError(message(cause)); setLoading(false); setBusy(false); denied.current?.();
    const unit = selectedUnit.current;
    if (unit) {
      const generation = scopeEpoch.current;
      void read<{ capabilities: string[] }>("/qms-access/effective?unit_id=" + encodeURIComponent(unit)).then((data) => {
        if (generation === scopeEpoch.current && Array.isArray(data.capabilities)) setCapabilities(data.capabilities.filter((value) => typeof value === "string"));
      }).catch(() => { /* The context remains closed until an explicit refresh. */ });
    }
  }, []);
  const unit = units.find((row) => row.id === unitId);
  return <section className="ncr-panel ia-workspace" aria-labelledby="internal-audits-heading" aria-busy={loading || busy}>
    <div className="workspace-heading"><div><p className="eyebrow">Quality assurance</p><h2 id="internal-audits-heading"><ClipboardList aria-hidden="true" size={23} /> Internal audits</h2><p>Plan audit programs, schedule audits and record controlled planning decisions.</p></div>
      <button type="button" className="secondary-action compact-action" aria-label="Refresh planning workspace" disabled={busy} onClick={() => { ++scopeEpoch.current; setCapabilities([]); setBlocked(false); setError(""); setLoading(true); setRefresh((value) => value + 1); }}><RefreshCw aria-hidden="true" size={16} />Refresh</button></div>
    <p className="ia-planning-note"><CalendarDays aria-hidden="true" size={17} />Planning workspace. Scope criteria, team, independence decisions, evidence and findings are still pending; a scheduled audit is not ready for execution.</p>
    <div className="ia-toolbar"><label>Organization scope<select value={unitId} disabled={busy || !units.length} onChange={(event) => {
      if (event.target.value === unitId) return;
      ++scopeEpoch.current; selectedUnit.current = event.target.value; setUnitId(event.target.value); setCapabilities([]); setBlocked(false); setError(""); setLoading(!!event.target.value); scopeChange.current?.(event.target.value);
    }}><option value="">Select a unit</option>{units.map((row) => <option key={row.id} value={row.id}>{row.name} · {row.code}</option>)}</select></label></div>
    {error && <p role="alert" className="denied-state">{error}</p>}
    {loading ? <RecordWorkspaceSkeleton label="Loading audit planning scopes and responsibilities" /> : blocked ? <p className="ncr-empty">The planning context was closed. Refresh the workspace to review your current responsibilities.</p> : !unit ? <p className="ncr-empty">Select an active organization unit to review audit planning.</p> : !capabilities.includes("audits.read") ? <p className="ncr-empty">No audit read responsibility is assigned for this unit. Contact the organization owner.</p> : <PlanningScope key={unit.id + "-" + refresh} unit={unit} capabilities={capabilities} onAccessError={invalidate} onBusyChange={setBusy} />}
  </section>;
}
