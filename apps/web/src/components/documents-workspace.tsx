"use client";

import { FileCheck2, FilePlus2, RefreshCw, ShieldCheck, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Unit = { id: string; code: string; name: string; status: string };
type Capability = { unit_id: string; capabilities: string[] };
type ProcessRef = { id: string; code: string; name: string };
type Member = { id: string; display_name: string; role: string };
type DocumentRow = { id: string; unit_id: string; process_id: string; code: string; title: string; document_type: string; owner_user_id: string | null; status: string; current_revision_id: string | null; row_version: number; created_at: string };
type Revision = { id: string; document_id: string; revision: string; status: string; prepared_by_user_id: string; prepared_by_display_name: string; reviewed_by_user_id: string | null; reviewed_by_display_name: string | null; approved_by_user_id: string | null; approved_by_display_name: string | null; change_summary: string; revision_date: string; effective_date: string | null; review_date: string | null; file_state: string; file_sha256: string | null; file_size: number | null; row_version: number; created_at: string };
const api = "/api/identity";
const canView = (caps: string[]) => ["documents.read", "documents.author", "documents.review", "documents.approve", "documents.release", "documents.obsolete"].some((cap) => caps.includes(cap));
function csrf(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

export function DocumentsWorkspace({ userId, onAccessDenied, preferredUnitId, onUnitChange }: { userId: string; onAccessDenied?: () => void; preferredUnitId?: string; onUnitChange?: (unitId: string) => void }) {
  const [initialPreferredUnitId] = useState(preferredUnitId ?? "");
  const [units, setUnits] = useState<Unit[]>([]);
  const [unitId, setUnitId] = useState("");
  const [caps, setCaps] = useState<string[]>([]);
  const [processes, setProcesses] = useState<ProcessRef[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [processSearch, setProcessSearch] = useState("");
  const [memberSearch, setMemberSearch] = useState("");
  const [processOffset, setProcessOffset] = useState(0);
  const [memberOffset, setMemberOffset] = useState(0);
  const [processHasNext, setProcessHasNext] = useState(false);
  const [memberHasNext, setMemberHasNext] = useState(false);
  const [rows, setRows] = useState<DocumentRow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [selectedRevision, setSelectedRevision] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [createDocument, setCreateDocument] = useState(false);
  const [createRevision, setCreateRevision] = useState(false);
  const [confirmObsolete, setConfirmObsolete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scopeLoading, setScopeLoading] = useState(false);
  const [verifiedUnitId, setVerifiedUnitId] = useState("");
  const [referenceGeneration, setReferenceGeneration] = useState(0);
  const [referencesReady, setReferencesReady] = useState(false);
  const [referenceError, setReferenceError] = useState("");
  const scopeEpoch = useRef(0);
  const scopeRequest = useRef<AbortController | null>(null);
  const [unitsLoading, setUnitsLoading] = useState(true);
  const [message, setMessage] = useState("Loading document access…");
  const [error, setError] = useState("");

  const selected = verifiedUnitId === unitId ? rows.find((row) => row.id === selectedId && row.unit_id === unitId) ?? null : null;
  const revision = revisions.find((row) => row.id === selectedRevision && row.document_id === selected?.id) ?? null;
  const verifiedCaps = verifiedUnitId === unitId ? caps : [];
  const canAuthor = verifiedCaps.includes("documents.author");
  const canReadProcesses = verifiedCaps.includes("processes.read");
  const canCreateDocument = canAuthor && canReadProcesses && referencesReady;
  const canReview = verifiedCaps.includes("documents.review");
  const canApprove = verifiedCaps.includes("documents.approve");
  const canRelease = verifiedCaps.includes("documents.release");
  const canObsolete = verifiedCaps.includes("documents.obsolete");

  const loadUnits = useCallback(async (signal?: AbortSignal) => {
    const response = await fetch(`${api}/organization/units?limit=100`, { credentials: "include", signal });
    if (!response.ok) throw new Error("Organizational units could not be loaded.");
    const data = await response.json() as Unit[];
    if (signal?.aborted) return;
    setUnits(data.filter((unit) => unit.status === "active"));
    const nextUnit = data.find((unit) => unit.id === initialPreferredUnitId && unit.status === "active")?.id
      ?? data.find((unit) => unit.status === "active")?.id ?? "";
    setUnitId(nextUnit);
  }, [initialPreferredUnitId]);

  const loadScope = useCallback(async (unit: string, signal?: AbortSignal, pageOffset = 0, filter = "") => {
    if (signal?.aborted) return;
    const epoch = ++scopeEpoch.current;
    scopeRequest.current?.abort();
    const controller = new AbortController();
    scopeRequest.current = controller;
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    const current = () => !controller.signal.aborted && epoch === scopeEpoch.current;
    setScopeLoading(Boolean(unit)); setReferenceError(""); setError(""); setMessage(""); setVerifiedUnitId(""); setCaps([]); setProcesses([]); setMembers([]); setReferencesReady(false); setProcessHasNext(false); setMemberHasNext(false); setRows([]); setRevisions([]); setSelectedId(""); setSelectedRevision(""); setOffset(pageOffset); setHasNext(false); setCreateDocument(false); setCreateRevision(false); setConfirmObsolete(false);
    try {
      if (!unit) { setMessage("No active organizational unit is available."); return; }
      const accessResponse = await fetch(`${api}/qms-access/effective?unit_id=${encodeURIComponent(unit)}`, { credentials: "include", signal: controller.signal });
      if (!current()) return;
      if (!accessResponse.ok) throw new Error(accessResponse.status === 401 ? "Your session has expired. Sign in again." : "Unit permissions could not be verified.");
      const access = await accessResponse.json() as Capability;
      if (!current()) return;
      if (access.unit_id !== unit) throw new Error("Unit permissions did not match the requested scope.");
      if (!canView(access.capabilities)) { setMessage("No document responsibilities are assigned for this unit."); return; }
      const query = new URLSearchParams({ unit_id: unit, limit: "50", offset: String(pageOffset), search: filter });
      const response = await fetch(`${api}/documents?${query}`, { credentials: "include", signal: controller.signal });
      if (!current()) return;
      if (!response.ok) throw new Error("Document register could not be loaded. Refresh your access.");
      const docs = await response.json() as DocumentRow[];
      if (!current()) return;
      setVerifiedUnitId(unit); setCaps(access.capabilities); setReferenceGeneration(epoch);
      setRows(docs.slice(0, 50)); setSelectedId(docs[0]?.id ?? "");
      setHasNext(docs.length > 50); setOffset(pageOffset); setAppliedSearch(filter);
      setMessage(docs.length ? "" : "No controlled documents in this unit yet.");
    } catch (cause) {
      if (current()) setError(cause instanceof Error ? cause.message : "Document service unavailable.");
    } finally {
      signal?.removeEventListener("abort", abort);
      if (current()) setScopeLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!unitId || !canAuthor || !canReadProcesses) return;
    const controller = new AbortController();
    const epoch = referenceGeneration;
    const current = () => !controller.signal.aborted && epoch === scopeEpoch.current;
    const timer = window.setTimeout(() => {
      if (!current()) return;
      setReferenceError(""); setReferencesReady(false); setProcesses([]); setMembers([]); setProcessHasNext(false); setMemberHasNext(false);
      const processQuery = new URLSearchParams({ unit_id: unitId, limit: "50", offset: String(processOffset), search: processSearch });
      const memberQuery = new URLSearchParams({ limit: "50", offset: String(memberOffset), search: memberSearch });
      void Promise.all([
        fetch(`${api}/documents/processes?${processQuery}`, { credentials: "include", signal: controller.signal }),
        fetch(`${api}/organization/members?${memberQuery}`, { credentials: "include", signal: controller.signal }),
      ]).then(async ([processResponse, memberResponse]) => {
        if (!processResponse.ok || !memberResponse.ok) throw new Error("Document creation references could not be loaded.");
        const [processRows, memberRows] = await Promise.all([processResponse.json() as Promise<ProcessRef[]>, memberResponse.json() as Promise<Member[]>]);
        if (current()) {
          setProcesses(processRows); setMembers(memberRows);
          setProcessHasNext(processRows.length === 50); setMemberHasNext(memberRows.length === 50);
          setReferencesReady(true);
        }
      }).catch(() => { if (current()) { setProcesses([]); setMembers([]); setReferencesReady(false); setReferenceError("Document creation references could not be loaded. Refresh or adjust the reference search to retry."); } });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, canAuthor, canReadProcesses, referenceGeneration, processSearch, memberSearch, processOffset, memberOffset]);

  useEffect(() => () => {
    ++scopeEpoch.current;
    scopeRequest.current?.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void loadUnits(controller.signal)
        .catch(() => { if (!controller.signal.aborted) setError("Organizational units could not be loaded."); })
        .finally(() => { if (!controller.signal.aborted) setUnitsLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [loadUnits]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => { void loadScope(unitId, controller.signal); }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, loadScope]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void fetch(`${api}/documents/${selected.id}/revisions`, { credentials: "include", signal: controller.signal })
        .then(async (response) => { if (!response.ok) throw new Error("Revision history unavailable."); return await response.json() as Revision[]; })
        .then((data) => { if (!controller.signal.aborted) { setRevisions(data); setSelectedRevision(data[0]?.id ?? ""); } })
        .catch(() => { if (!controller.signal.aborted) { setRevisions([]); setSelectedRevision(""); setError("Revision history could not be loaded."); } });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [selected]);

  const processName = useMemo(() => new Map(processes.map((item) => [item.id, `${item.code} · ${item.name}`])), [processes]);

  async function jsonMutation(path: string, body: object, method = "POST") {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}${path}`, { method, credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() }, body: JSON.stringify(body) });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) { setCaps([]); setRows([]); setRevisions([]); onAccessDenied?.(); }
        throw new Error(response.status === 409 ? "This record changed or its workflow state no longer permits that action. Refresh the register." : response.status === 403 ? "Your document responsibility is no longer active." : response.status === 401 ? "Your session has expired. Sign in again." : "The change could not be saved.");
      }
      await loadScope(unitId, undefined, offset, appliedSearch);
      setMessage("The change was saved and recorded in the audit trail.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Document service unavailable."); }
    finally { setBusy(false); }
  }

  async function addDocument(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!canAuthor || !unitId || busy) return;
    if (!referencesReady || !canReadProcesses) return;
    const data = new FormData(event.currentTarget);
    if (!processes.some((process) => process.id === data.get("process_id"))) return;
    await jsonMutation("/documents", { unit_id: unitId, process_id: data.get("process_id"), code: data.get("code"), title: data.get("title"), document_type: data.get("document_type"), owner_user_id: data.get("owner_user_id") || null });
    setCreateDocument(false);
  }

  async function addRevision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selected || !canAuthor || busy) return;
    const data = new FormData(event.currentTarget);
    await jsonMutation(`/documents/${selected.id}/revisions`, { revision: data.get("revision"), change_summary: data.get("change_summary"), revision_date: data.get("revision_date") });
    setCreateRevision(false);
  }

  async function uploadFile(file: File | undefined) {
    if (!selected || !revision || !file || !canAuthor || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${api}/documents/${selected.id}/revisions/${revision.id}/file`, { method: "PUT", credentials: "include", headers: { "Content-Type": file.type || "application/octet-stream", "X-CSRF-Token": csrf() }, body: file });
      if (!response.ok) throw new Error(response.status === 503 ? "The security scanner is unavailable or its signatures are stale. No file was accepted." : response.status === 415 ? "Only a valid PDF file is accepted." : response.status === 413 ? "The PDF exceeds the 20 MiB limit." : "The PDF could not be uploaded.");
      const result = await response.json() as { file_state: string };
      await loadScope(unitId, undefined, offset, appliedSearch);
      setMessage(result.file_state === "clean" ? "PDF accepted after the security scan." : "The scanner rejected this file; it is unavailable for use.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload unavailable."); }
    finally { setBusy(false); }
  }

  async function command(action: "submit" | "approve" | "reject" | "release") {
    if (!selected || !revision || busy) return;
    await jsonMutation(`/documents/${selected.id}/revisions/${revision.id}/${action}`, { expected_version: revision.row_version });
  }

  function closeDocumentForm() {
    setCreateDocument(false); setProcessSearch(""); setMemberSearch(""); setProcessOffset(0); setMemberOffset(0);
  }

  const formatSize = (size: number | null) => size == null ? "Not uploaded" : `${(size / (1024 * 1024)).toFixed(2)} MiB`;
  const formatDate = (value: string | null, includeTime = false) => {
    if (!value) return "Not recorded";
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
    const options: Intl.DateTimeFormatOptions = { dateStyle: "medium" };
    if (includeTime && !dateOnly) options.timeStyle = "short";
    if (dateOnly) options.timeZone = "UTC";
    return new Intl.DateTimeFormat(undefined, options).format(new Date(value));
  };
  return <section className="documents-workspace" aria-labelledby="documents-heading" aria-busy={scopeLoading}>
    <div className="workspace-heading"><div><p className="eyebrow">Controlled information</p><h2 id="documents-heading"><FileCheck2 aria-hidden="true" size={22} /> Document control</h2><p className="workspace-subtitle">Controlled revisions, independent review, approval and release.</p></div>
      <button className="secondary-action compact-action" type="button" disabled={busy || scopeLoading} onClick={() => void loadScope(unitId, undefined, offset, appliedSearch)}><RefreshCw size={16} aria-hidden="true" /> Refresh</button></div>
    <p className="qms-access-note"><ShieldCheck size={17} aria-hidden="true" /> Files are scanned before private storage. Access and workflow transitions are validated by the server.</p>
    {error && <p role="alert" className="denied-state">{error}</p>}{message && <p role={error ? "status" : "status"} className="workflow-message">{message}</p>}
    {unitsLoading || (scopeLoading && Boolean(unitId) && rows.length === 0 && !error) ? <RecordWorkspaceSkeleton label="Loading document control" /> : <>
    <div className="documents-toolbar"><label htmlFor="documents-unit">Organizational unit<select id="documents-unit" value={unitId} disabled={busy} onChange={(event) => { setOffset(0); setProcessOffset(0); setMemberOffset(0); setProcessSearch(""); setMemberSearch(""); setCreateDocument(false); setCreateRevision(false); setConfirmObsolete(false); setUnitId(event.target.value); onUnitChange?.(event.target.value); }}><option value="">Select a unit</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}</option>)}</select></label>
      <form className="document-search" onSubmit={(event) => { event.preventDefault(); void loadScope(unitId, undefined, 0, search.trim()); }}><label htmlFor="document-search">Find by code or title<input id="document-search" maxLength={160} value={search} onChange={(event) => setSearch(event.target.value)} /></label><button className="secondary-action compact-action" type="submit" disabled={busy || scopeLoading}>Search</button></form>
      {canAuthor && <button className="primary-action compact-action" type="button" disabled={busy || scopeLoading || !canCreateDocument} onClick={() => setCreateDocument((value) => !value)}><FilePlus2 size={16} aria-hidden="true" /> New document</button>}</div>
    {canAuthor && !canReadProcesses && <p className="qms-history-caption">Document creation also requires process read access so each controlled document can be linked to an authorized active process.</p>}
    {canAuthor && canReadProcesses && !referencesReady && !referenceError && <p className="qms-history-caption" role="status">Loading authorized processes and owners…</p>}
    {referenceError && canAuthor && canReadProcesses && <p className="denied-state document-reference-error" role="alert">{referenceError}</p>}
    {createDocument && canAuthor && canReadProcesses && <form className="document-form" onSubmit={(event) => void addDocument(event)}><h3>Register a controlled document</h3><fieldset disabled={busy || scopeLoading}>
      <label>Code<input name="code" required maxLength={40} /></label><label>Title<input name="title" required maxLength={200} /></label>
      <label>Document type<select name="document_type"><option value="procedure">Procedure</option><option value="policy">Policy</option><option value="work_instruction">Work instruction</option><option value="form">Form</option><option value="record_template">Record template</option><option value="manual">Manual</option><option value="other">Other</option></select></label>
      <label>Find process<input maxLength={160} value={processSearch} onChange={(event) => { setReferencesReady(false); setProcessSearch(event.target.value); setProcessOffset(0); }} placeholder="Search code or name" /></label>
      <nav className="document-pagination" aria-label="Process search pages"><button type="button" className="secondary-action compact-action" disabled={processOffset === 0} onClick={() => { setReferencesReady(false); setProcessOffset(Math.max(0, processOffset - 50)); }}>Previous processes</button><span>Results {processOffset + (processes.length ? 1 : 0)}–{processOffset + processes.length}</span><button type="button" className="secondary-action compact-action" disabled={!processHasNext} onClick={() => { setReferencesReady(false); setProcessOffset(processOffset + 50); }}>More processes</button></nav>
      <label>Process<select name="process_id" required disabled={!referencesReady}><option value="">Select an active process</option>{processes.map((process) => <option key={process.id} value={process.id}>{process.code} · {process.name}</option>)}</select></label>
      {referencesReady && processes.length === 0 && <p className="qms-history-caption">No active processes match this search. Adjust the process search before creating the document.</p>}
      <label>Find document owner<input maxLength={160} value={memberSearch} onChange={(event) => { setReferencesReady(false); setMemberSearch(event.target.value); setMemberOffset(0); }} placeholder="Search tenant members" /></label>
      <nav className="document-pagination" aria-label="Member search pages"><button type="button" className="secondary-action compact-action" disabled={memberOffset === 0} onClick={() => { setReferencesReady(false); setMemberOffset(Math.max(0, memberOffset - 50)); }}>Previous members</button><span>Results {memberOffset + (members.length ? 1 : 0)}–{memberOffset + members.length}</span><button type="button" className="secondary-action compact-action" disabled={!memberHasNext} onClick={() => { setReferencesReady(false); setMemberOffset(memberOffset + 50); }}>More members</button></nav>
      <label>Document owner (optional)<select name="owner_user_id" disabled={!referencesReady}><option value="">No owner assigned</option>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name} · {member.role}</option>)}</select></label>
      <div className="document-form-actions"><button className="primary-action compact-action" type="submit" disabled={!referencesReady || processes.length === 0}>Create document</button><button className="secondary-action compact-action" type="button" onClick={closeDocumentForm}>Cancel</button></div>
    </fieldset></form>}
    <div className="documents-grid"><aside className="document-list"><h3>Register <span>{rows.length}</span></h3>{rows.length ? <ul>{rows.map((row) => <li key={row.id}><button type="button" disabled={busy || scopeLoading} className={row.id === selectedId ? "selected" : ""} onClick={() => { setRevisions([]); setSelectedRevision(""); setSelectedId(row.id); setCreateRevision(false); setConfirmObsolete(false); }}><strong>{row.code}</strong><span>{row.title}</span><small>{row.status} · {row.document_type}</small></button></li>)}</ul> : <p className="workspace-subtitle">No documents to display.</p>}</aside>
      <div className="document-detail">{selected ? <><div className="detail-heading"><div><p className="eyebrow">{selected.code}</p><h3>{selected.title}</h3><p>{processName.get(selected.process_id) ?? "Linked process"} · {selected.status}</p></div><div className="document-heading-actions">{canAuthor && selected.status !== "obsolete" && <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setCreateRevision((value) => !value)}>New revision</button>}{canObsolete && selected.status !== "obsolete" && (confirmObsolete ? <><button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => { void jsonMutation(`/documents/${selected.id}/obsolete`, { expected_version: selected.row_version }); setConfirmObsolete(false); }}>Confirm obsolete</button><button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setConfirmObsolete(false)}>Cancel</button></> : <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setConfirmObsolete(true)}>Obsolete</button>)}</div></div>
        {createRevision && canAuthor && <form className="document-form" onSubmit={(event) => void addRevision(event)}><h4>Prepare a revision</h4><fieldset disabled={busy}><label>Revision code<input name="revision" required maxLength={40} /></label><label>Revision date<input name="revision_date" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} /></label><label className="document-wide">Change summary<textarea name="change_summary" maxLength={4000} rows={3} /></label><div className="document-form-actions"><button className="primary-action compact-action" type="submit">Create revision</button><button className="secondary-action compact-action" type="button" onClick={() => setCreateRevision(false)}>Cancel</button></div></fieldset></form>}
        <h4 className="revision-heading">Revision history</h4>{revisions.length ? <div className="revision-table-scroll"><table className="qms-access-table"><thead><tr><th>Revision</th><th>Status</th><th>File</th><th>Prepared</th></tr></thead><tbody>{revisions.map((item) => <tr key={item.id}><td><button type="button" className="revision-select" onClick={() => setSelectedRevision(item.id)} aria-pressed={item.id === selectedRevision}>{item.revision}</button></td><td>{item.status}</td><td>{item.file_state} · {formatSize(item.file_size)}</td><td><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleDateString()}</time></td></tr>)}</tbody></table></div> : <p className="workspace-subtitle">No revisions yet.</p>}
        {revision && <div className="revision-actions"><div><strong>Revision {revision.revision}</strong><p>{revision.change_summary || "No change summary provided."}</p>{revision.file_sha256 && <small>SHA-256 · {revision.file_sha256}</small>}</div>
          <dl className="revision-decisions"><div><dt>Revision date</dt><dd>{formatDate(revision.revision_date)}</dd></div><div><dt>Prepared by</dt><dd>{revision.prepared_by_display_name ?? `User ${revision.prepared_by_user_id.slice(0, 8)}`} · {formatDate(revision.created_at, true)}</dd></div><div><dt>Reviewed by</dt><dd>{revision.reviewed_by_display_name ?? (revision.reviewed_by_user_id ? `User ${revision.reviewed_by_user_id.slice(0, 8)}` : "Not reviewed")}{revision.review_date && ` · ${formatDate(revision.review_date)}`}</dd></div><div><dt>Approved by</dt><dd>{revision.approved_by_display_name ?? (revision.approved_by_user_id ? `User ${revision.approved_by_user_id.slice(0, 8)}` : "Not approved")}{revision.approved_by_user_id && revision.review_date && ` · ${formatDate(revision.review_date)}`}</dd></div><div><dt>Effective date</dt><dd>{formatDate(revision.effective_date)}</dd></div></dl>
          {canAuthor && revision.status === "draft" && revision.file_state === "missing" && <label className="upload-control"><Upload size={16} aria-hidden="true" /> Attach PDF<input type="file" accept="application/pdf,.pdf" disabled={busy} onChange={(event) => { void uploadFile(event.target.files?.[0]); event.currentTarget.value = ""; }} /></label>}
          {canReview && ["draft", "rejected"].includes(revision.status) && <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => void command("submit")}>Submit for review</button>}
          {canReview && revision.status === "under_review" && <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => void command("reject")}>Reject</button>}
          {canApprove && revision.status === "under_review" && <button type="button" className="primary-action compact-action" disabled={busy || revision.file_state !== "clean" || revision.prepared_by_user_id === userId} onClick={() => void command("approve")}>Approve</button>}
          {canRelease && revision.status === "approved" && <button type="button" className="primary-action compact-action" disabled={busy || revision.file_state !== "clean"} onClick={() => void command("release")}>Release</button>}
          {revision.file_state === "clean" && caps.includes("documents.read") && <a className="secondary-action compact-action" href={`${api}/documents/${selected.id}/revisions/${revision.id}/file`}>Download PDF</a>}
        </div>}
      </> : <div className="empty-state"><FileCheck2 size={22} aria-hidden="true" /><div><strong>Select a document</strong><p>Choose a record to inspect its revisions and controlled status.</p></div></div>}</div>
    </div>
    <nav className="document-pagination" aria-label="Document register pages"><button type="button" className="secondary-action compact-action" disabled={busy || scopeLoading || offset === 0} onClick={() => void loadScope(unitId, undefined, Math.max(0, offset - 50), appliedSearch)}>Previous</button><span>Showing {rows.length ? offset + 1 : 0}–{offset + rows.length}</span><button type="button" className="secondary-action compact-action" disabled={busy || scopeLoading || !hasNext} onClick={() => void loadScope(unitId, undefined, offset + 50, appliedSearch)}>Next</button></nav>
    </>}
  </section>;
}
