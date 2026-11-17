"use client";

import { FileCheck2, RefreshCw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

type Audit = { id: string; unit_id: string; code: string; state: string; row_version: number; planned_end?: string };
type Review = {
  id: string; audit_id: string; unit_id: string; team_member_id: string; subject_user_id: string;
  subject_name_snapshot: string; review_version: number; source_audit_version: number;
  decision: "confirmed" | "withdrawn"; notes: string; competence_attested: boolean;
  document_id: string; document_revision_id: string; document_code_snapshot: string;
  document_title_snapshot: string; document_revision_snapshot: string; file_sha256: string;
  valid_until: string; reviewer_user_id: string; reviewer_name_snapshot: string; created_at: string;
};
type Auditor = {
  team_member_id: string; user_id: string; display_name_snapshot: string; member_active: boolean;
  assignment_active: boolean; assessment_status: string; latest_review: Review | null; review_current: boolean;
};
type Summary = {
  audit_id: string; unit_id: string; audit_version: number; actor_user_id: string; review_version: number;
  can_review: boolean; review_blockers: string[]; planned_auditors: number; current_assessments: number; auditors: Auditor[];
};
type DocumentChoice = { document_id: string; document_revision_id: string; code: string; title: string; revision: string; file_sha256: string };
const api = "/api/identity/internal-audits/audits/";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const hash = /^[0-9a-f]{64}$/i;
const statuses: Record<string, string> = {
  missing: "Not assessed", current: "Current assessment", withdrawn: "Withdrawn", outdated: "Plan changed",
  expired: "Expired or insufficient validity", evidence_unavailable: "Support no longer current",
  member_inactive: "Company membership inactive", reviewer_inactive: "Reviewer membership inactive", assignment_inactive: "Assignment no longer active",
};
function validId(value: unknown): value is string { return typeof value === "string" && uuid.test(value); }
function validHash(value: unknown): value is string { return typeof value === "string" && hash.test(value); }
class AccessError extends Error { constructor(readonly status: number) { super(String(status)); } }
const lostAccess = (cause: unknown) => cause instanceof AccessError && [401, 403, 404].includes(cause.status);
function failure(cause: unknown) {
  if (cause instanceof AccessError && cause.status === 503) return "The service is temporarily unavailable. Your draft is preserved; retry when available.";
  if (cause instanceof AccessError && cause.status === 409) return "The plan, support or competence history changed. Refresh competence before another decision.";
  if (cause instanceof AccessError && cause.status === 422) return "Check the support, validity and explicit assessment affirmation.";
  return "The competence result could not be confirmed. Refresh competence and inspect history before submitting again.";
}
function validDate(value: string) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
}
function validReview(row: Review, audit: Audit) {
  return row && typeof row === "object" && validId(row.id) && row.audit_id === audit.id && row.unit_id === audit.unit_id
    && validId(row.team_member_id) && validId(row.subject_user_id) && typeof row.subject_name_snapshot === "string" && row.subject_name_snapshot.length > 0
    && Number.isInteger(row.review_version) && row.review_version > 0 && Number.isInteger(row.source_audit_version) && row.source_audit_version > 0 && row.source_audit_version <= audit.row_version
    && ["confirmed", "withdrawn"].includes(row.decision) && row.competence_attested === (row.decision === "confirmed") && typeof row.notes === "string" && row.notes.trim().length > 0
    && validId(row.document_id) && validId(row.document_revision_id) && typeof row.document_code_snapshot === "string" && row.document_code_snapshot.length > 0
    && typeof row.document_title_snapshot === "string" && row.document_title_snapshot.length > 0 && typeof row.document_revision_snapshot === "string" && row.document_revision_snapshot.length > 0
    && validHash(row.file_sha256) && validDate(row.valid_until) && validId(row.reviewer_user_id) && typeof row.reviewer_name_snapshot === "string" && row.reviewer_name_snapshot.length > 0
    && typeof row.created_at === "string" && Number.isFinite(Date.parse(row.created_at));
}
function validSummary(data: Summary, audit: Audit) {
  if (!data || data.audit_id !== audit.id || data.unit_id !== audit.unit_id || data.audit_version !== audit.row_version || !validId(data.actor_user_id)
    || !Number.isInteger(data.review_version) || data.review_version < 0 || typeof data.can_review !== "boolean" || !Array.isArray(data.review_blockers) || data.review_blockers.some(item => typeof item !== "string")
    || !Number.isInteger(data.planned_auditors) || data.planned_auditors < 0 || !Number.isInteger(data.current_assessments) || data.current_assessments < 0 || data.current_assessments > data.planned_auditors
    || !Array.isArray(data.auditors) || data.auditors.length > 21 || new Set(data.auditors.map(row => row.team_member_id)).size !== data.auditors.length) return false;
  return data.auditors.every(row => row && validId(row.team_member_id) && validId(row.user_id) && typeof row.display_name_snapshot === "string" && row.display_name_snapshot.length > 0
    && typeof row.member_active === "boolean" && typeof row.assignment_active === "boolean" && typeof row.assessment_status === "string" && Object.hasOwn(statuses, row.assessment_status) && typeof row.review_current === "boolean"
    && (row.latest_review === null || validReview(row.latest_review, audit) && row.latest_review.team_member_id === row.team_member_id && row.latest_review.subject_user_id === row.user_id && row.latest_review.review_version <= data.review_version)
    && row.review_current === (row.assessment_status === "current") && (!row.review_current || audit.state === "planned" && row.assignment_active && row.member_active && row.latest_review?.decision === "confirmed" && row.latest_review.source_audit_version === audit.row_version && row.latest_review.valid_until >= new Date().toISOString().slice(0, 10) && (!audit.planned_end || row.latest_review.valid_until >= audit.planned_end)))
    && data.auditors.filter(row => row.assignment_active).length <= data.planned_auditors && data.auditors.filter(row => row.review_current).length <= data.current_assessments
    && (data.auditors.filter(row => row.assignment_active).length !== data.planned_auditors || data.auditors.filter(row => row.review_current).length === data.current_assessments);
}
function validChoice(row: DocumentChoice) {
  return row && validId(row.document_id) && validId(row.document_revision_id) && typeof row.code === "string" && row.code.length > 0 && typeof row.title === "string" && row.title.length > 0 && typeof row.revision === "string" && row.revision.length > 0 && validHash(row.file_sha256);
}
async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(api + path, { credentials: "include", signal });
  if (response.status !== 200) throw new AccessError(response.status);
  return await response.json() as T;
}

function SupportPicker({ auditId, disabled, onSelected, onAccessChanged }: {
  auditId: string; disabled: boolean; onSelected: (choice: DocumentChoice | null) => void; onAccessChanged: (status: number) => void;
}) {
  const [query, setQuery] = useState({ q: "", offset: 0, refresh: 0 });
  const [search, setSearch] = useState(""); const [rows, setRows] = useState<DocumentChoice[]>([]);
  const [selected, setSelected] = useState<DocumentChoice | null>(null); const [next, setNext] = useState(false);
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const callbacks = useRef({ onSelected, onAccessChanged });
  useEffect(() => { callbacks.current = { onSelected, onAccessChanged }; }, [onSelected, onAccessChanged]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true); setError(""); setRows([]); setNext(false);
      const params = new URLSearchParams({ q: query.q, limit: "21", offset: String(query.offset) });
      void read<DocumentChoice[]>(`${auditId}/competence/documents?${params}`, controller.signal).then(items => {
        if (controller.signal.aborted) return;
        if (!Array.isArray(items) || items.length > 21 || items.some(item => !validChoice(item)) || new Set(items.map(item => item.document_revision_id)).size !== items.length) throw new Error("Invalid support choices");
        setRows(items.slice(0, 20)); setNext(items.length > 20);
      }).catch(cause => { if (!controller.signal.aborted) { setError("The support choices could not be verified. Refresh the choices."); if (lostAccess(cause)) callbacks.current.onAccessChanged((cause as AccessError).status); } })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [auditId, query]);
  return <div className="ia-reference-picker">
    <div className="ia-reference-toolbar"><label>Find competence support<input value={search} maxLength={160} disabled={disabled} onChange={event => setSearch(event.target.value)} /></label><button type="button" className="secondary-action compact-action" disabled={disabled || loading} onClick={() => setQuery({ q: search.trim(), offset: 0, refresh: query.refresh + 1 })}>Search support</button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}
    <label>Released competence support<select required disabled={disabled || loading} value={selected?.document_revision_id ?? ""} onChange={event => { const choice = rows.find(row => row.document_revision_id === event.target.value) ?? (selected?.document_revision_id === event.target.value ? selected : null); setSelected(choice); callbacks.current.onSelected(choice); }}>
      <option value="">{loading ? "Loading released support…" : "Choose released, clean support"}</option>
      {selected && !rows.some(row => row.document_revision_id === selected.document_revision_id) && <option value={selected.document_revision_id}>{selected.code} · {selected.title} · {selected.revision}</option>}
      {rows.map(row => <option key={row.document_revision_id} value={row.document_revision_id}>{row.code} · {row.title} · {row.revision}</option>)}
    </select></label>
    {!loading && !rows.length && !error && <p className="qms-history-caption">No released support on this page. Change the search or release the relevant controlled document first.</p>}
    <div className="ia-pagination"><button type="button" className="secondary-action compact-action" disabled={disabled || loading || !query.offset} onClick={() => setQuery({ ...query, offset: Math.max(0, query.offset - 20) })}>Previous support</button><span>Page {query.offset / 20 + 1}</span><button type="button" className="secondary-action compact-action" disabled={disabled || loading || !next} onClick={() => setQuery({ ...query, offset: query.offset + 20 })}>More support</button></div>
  </div>;
}

export function InternalAuditCompetence({ audit, capabilities, disabled, onBusyChange, onAuditRefreshed, onAccessChanged, onRecorded }: {
  audit: Audit; capabilities: string[]; disabled: boolean; onBusyChange: (value: boolean) => void;
  onAuditRefreshed: (row: Audit) => void; onAccessChanged: (status: number) => void; onRecorded?: () => void;
}) {
  const heading = useId(); const canRead = capabilities.includes("audits.read") && capabilities.includes("documents.read"); const canReview = canRead && capabilities.includes("audits.review");
  const [data, setData] = useState<Summary | null>(null); const [history, setHistory] = useState<Review[]>([]);
  const [offset, setOffset] = useState(0); const [historyOffset, setHistoryOffset] = useState(0); const [nextHistory, setNextHistory] = useState(false);
  const [selectedId, setSelectedId] = useState(""); const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<{ mode: "confirmed" | "withdrawn"; member: Auditor } | null>(null); const [support, setSupport] = useState<DocumentChoice | null>(null);
  const source = useRef(audit); const pending = useRef(false); const reads = useRef(0); const operations = useRef(0);
  const callbacks = useRef({ onBusyChange, onAuditRefreshed, onAccessChanged, onRecorded });
  useEffect(() => { source.current = audit; callbacks.current = { onBusyChange, onAuditRefreshed, onAccessChanged, onRecorded }; }, [audit, onBusyChange, onAuditRefreshed, onAccessChanged, onRecorded]);
  useEffect(() => { const r = reads, o = operations, p = pending, c = callbacks; return () => { ++r.current; ++o.current; if (p.current) c.current.onBusyChange(false); }; }, []);
  useEffect(() => {
    const controller = new AbortController(); const token = ++reads.current; const current = () => !controller.signal.aborted && token === reads.current;
    const timer = window.setTimeout(() => {
      setData(null); setHistory([]); setNextHistory(false); setError(""); setLoading(true);
      if (!canRead) { setLoading(false); return; }
      void Promise.all([read<Summary>(`${audit.id}/competence?limit=21&offset=${offset}`, controller.signal), read<Review[]>(`${audit.id}/competence/reviews?limit=21&offset=${historyOffset}`, controller.signal)])
        .then(([summary, rows]) => {
          if (!current()) return;
          if (!validSummary(summary, source.current) || !Array.isArray(rows) || rows.length > 21 || rows.some(row => !validReview(row, source.current) || row.review_version > summary.review_version) || new Set(rows.map(row => row.id)).size !== rows.length || rows.some((row, index) => index > 0 && row.review_version >= rows[index - 1].review_version) || (historyOffset === 0 && (rows[0]?.review_version ?? 0) !== summary.review_version)) throw new Error("Mismatched competence response");
          setData(summary); setHistory(rows.slice(0, 20)); setNextHistory(rows.length > 20);
          setSelectedId(value => summary.auditors.slice(0, 20).some(row => row.team_member_id === value) ? value : summary.auditors[0]?.team_member_id ?? "");
        }).catch(cause => { if (current()) { setError(failure(cause)); setBlocked(true); if (lostAccess(cause)) callbacks.current.onAccessChanged((cause as AccessError).status); } })
        .finally(() => { if (current()) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [audit.id, audit.unit_id, audit.row_version, canRead, offset, historyOffset, refresh]);
  useEffect(() => { const timer = window.setTimeout(() => { setEditor(null); setSupport(null); setBlocked(false); setNotice(""); }, 0); return () => window.clearTimeout(timer); }, [audit.id, audit.row_version]);

  async function reconcile() {
    if (pending.current || disabled) return;
    const token = ++operations.current; setLoading(true); setError("");
    try {
      const row = await read<Audit>(audit.id);
      if (token !== operations.current) return;
      if (row.id !== audit.id || row.unit_id !== audit.unit_id || !Number.isInteger(row.row_version) || row.row_version < 1) throw new Error("Mismatched parent");
      callbacks.current.onAuditRefreshed(row); setBlocked(false); setEditor(null); setSupport(null); setNotice(""); setOffset(0); setHistoryOffset(0); setRefresh(value => value + 1);
    } catch (cause) { if (token === operations.current) { setLoading(false); setBlocked(true); setError(failure(cause)); if (lostAccess(cause)) callbacks.current.onAccessChanged((cause as AccessError).status); } }
  }

  async function submit(notes: string, until: string | null, affirmed: boolean) {
    if (!data || !editor || pending.current || disabled || loading || blocked || !canReview || !data.can_review) return;
    const snapshot = data; const target = editor; const proof = support; const previous = target.member.latest_review;
    if (target.mode === "confirmed" && (!target.member.assignment_active || !target.member.member_active || !proof || !until || !affirmed)) return;
    if (target.mode === "withdrawn" && (!previous || previous.decision !== "confirmed")) return;
    const token = ++operations.current; pending.current = true; setBusy(true); callbacks.current.onBusyChange(true); setError(""); setNotice(""); let received = false;
    const body = { expected_audit_version: snapshot.audit_version, expected_review_version: snapshot.review_version, team_member_id: target.member.team_member_id, decision: target.mode, notes, competence_attested: target.mode === "confirmed" && affirmed, document_id: target.mode === "confirmed" ? proof!.document_id : null, document_revision_id: target.mode === "confirmed" ? proof!.document_revision_id : null, valid_until: target.mode === "confirmed" ? until : null };
    try {
      const cookie = document.cookie.split("; ").find(item => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}${audit.id}/competence/reviews`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" }, body: JSON.stringify(body) }); received = true;
      if (token !== operations.current) return;
      if (!response.ok) { if ([401, 403, 404].includes(response.status)) { setData(null); setHistory([]); setEditor(null); setSupport(null); callbacks.current.onAccessChanged(response.status); return; } if (![422, 503].includes(response.status)) setBlocked(true); throw new AccessError(response.status); }
      setBlocked(true);
      if (response.status !== 201) throw new Error("Unconfirmed competence command");
      const result = await response.json() as { review: Review; audit_version: number };
      if (token !== operations.current) return;
      const row = result.review;
      if (!validReview(row, audit) || result.audit_version !== snapshot.audit_version || row.source_audit_version !== snapshot.audit_version || row.review_version !== snapshot.review_version + 1 || row.reviewer_user_id !== snapshot.actor_user_id || row.team_member_id !== target.member.team_member_id || row.subject_user_id !== target.member.user_id || row.subject_name_snapshot !== target.member.display_name_snapshot || row.decision !== body.decision || row.notes !== body.notes || row.competence_attested !== body.competence_attested || history.some(item => item.id === row.id)
        || (target.mode === "confirmed" ? row.document_id !== proof!.document_id || row.document_revision_id !== proof!.document_revision_id || row.file_sha256 !== proof!.file_sha256 || row.document_code_snapshot !== proof!.code || row.document_title_snapshot !== proof!.title || row.document_revision_snapshot !== proof!.revision || row.valid_until !== until : row.document_id !== previous!.document_id || row.document_revision_id !== previous!.document_revision_id || row.file_sha256 !== previous!.file_sha256 || row.document_code_snapshot !== previous!.document_code_snapshot || row.document_title_snapshot !== previous!.document_title_snapshot || row.document_revision_snapshot !== previous!.document_revision_snapshot || row.valid_until !== previous!.valid_until)) throw new Error("Mismatched recorded competence");
      setData(null); setHistory([]); setLoading(true); setBlocked(false); setEditor(null); setSupport(null); setOffset(0); setHistoryOffset(0); setNotice(target.mode === "confirmed" ? "Competence assessment recorded for this auditor and planning version. Execution remains blocked." : "Competence assessment withdrawn. Its supporting record and history are preserved."); setRefresh(value => value + 1); callbacks.current.onRecorded?.();
    } catch (cause) { if (token === operations.current) { if (!received) setBlocked(true); setError(failure(cause)); } }
    finally { if (token === operations.current) { pending.current = false; setBusy(false); callbacks.current.onBusyChange(false); } }
  }

  if (!capabilities.includes("audits.read")) return null;
  if (!canRead) return <p className="qms-history-caption">A documents.read responsibility is required to inspect competence support.</p>;
  const member = data?.auditors.slice(0, 20).find(row => row.team_member_id === selectedId);
  const locked = busy || disabled || loading || blocked;
  const minimumDate = [audit.planned_end ?? "", new Date().toISOString().slice(0, 10)].sort().at(-1);
  return <section className="ncr-read-section" aria-labelledby={heading} aria-busy={loading || busy}>
    <div className="related-capas-heading"><div><h4 id={heading}><FileCheck2 size={17} aria-hidden="true" /> Auditor competence assessments</h4><p>Record a human assessment supported by a released document. This does not certify competence or authorize execution.</p></div><button type="button" className="icon-button" aria-label="Refresh competence" disabled={busy || disabled} onClick={() => void reconcile()}><RefreshCw size={16} aria-hidden="true" /></button></div>
    {error && <p className="error-notice" role="alert">{error}</p>}{notice && <p className="success-notice" role="status">{notice}</p>}
    {loading ? <div className="related-capa-loading" role="status" aria-label="Loading competence assessments"><span aria-hidden="true" /></div> : data && <>
      <p className="qms-history-caption">{data.current_assessments} of {data.planned_auditors} active planned auditors have a current recorded assessment. Plan version {data.audit_version} · Review version {data.review_version}.</p>
      {data.review_blockers.length > 0 && <details className="ncr-timeline"><summary>Why competence recording is unavailable</summary><ul>{data.review_blockers.map(reason => <li key={reason}>{reason}</li>)}</ul></details>}
      {data.auditors.length ? <><label>Competence auditor<select value={selectedId} disabled={!!editor || busy || disabled} onChange={event => setSelectedId(event.target.value)}>{data.auditors.slice(0, 20).map(row => <option key={row.team_member_id} value={row.team_member_id}>{row.display_name_snapshot}{row.assignment_active ? "" : " · former assignment"}</option>)}</select></label>
        {member && <div className="ia-scope-summary"><strong>{statuses[member.assessment_status]}</strong>{member.latest_review && <><p>{member.latest_review.document_code_snapshot} · {member.latest_review.document_revision_snapshot} · Valid through {member.latest_review.valid_until} UTC</p><p>{member.latest_review.notes}</p><small>Recorded by {member.latest_review.reviewer_name_snapshot} for plan version {member.latest_review.source_audit_version}</small></>}
          {canReview && data.can_review && !editor && <div className="ncr-form-actions">{member.assignment_active && member.member_active && <button type="button" className="secondary-action compact-action" disabled={locked} onClick={() => { setEditor({ mode: "confirmed", member }); setSupport(null); }}>Record competence assessment</button>}{member.latest_review?.decision === "confirmed" && <button type="button" className="secondary-action compact-action" disabled={locked} onClick={() => { setEditor({ mode: "withdrawn", member }); setSupport(null); }}>Withdraw competence assessment</button>}</div>}
        </div>}
      </> : <p className="qms-history-caption">No auditor assignments or recorded competence assessments on this page.</p>}
      <div className="ia-pagination"><button type="button" className="secondary-action compact-action" disabled={!!editor || busy || disabled || !offset} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous competence auditors</button><span>Page {offset / 20 + 1}</span><button type="button" className="secondary-action compact-action" disabled={!!editor || busy || disabled || data.auditors.length <= 20} onClick={() => setOffset(value => value + 20)}>More competence auditors</button></div>
    </>}
    {editor && data && <form className="ncr-editor" aria-label={editor.mode === "confirmed" ? "Record competence assessment" : "Withdraw competence assessment"} onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); const notes = String(form.get("notes") ?? "").trim(); if (!notes) return; void submit(notes, editor.mode === "confirmed" ? String(form.get("valid_until") ?? "") : null, editor.mode === "confirmed" && form.get("attested") === "on"); }}><fieldset className="ncr-editor-content" disabled={locked}><p className="qms-history-caption">{editor.member.display_name_snapshot} · Plan version {data.audit_version}. Assess the relevance of the support to this audit; a file is not an automatic qualification.</p>
      {editor.mode === "confirmed" && <><SupportPicker auditId={audit.id} disabled={locked} onSelected={setSupport} onAccessChanged={status => callbacks.current.onAccessChanged(status)} /><label>Competence valid through (UTC)<input name="valid_until" type="date" required min={minimumDate} /></label></>}
      <label>Competence rationale<textarea name="notes" required maxLength={2000} rows={4} /></label>
      {editor.mode === "confirmed" && <label className="ncr-check"><input type="checkbox" name="attested" required />I assessed this auditor&apos;s relevant competence and the supporting evidence for this audit.</label>}
      <div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={locked || (editor.mode === "confirmed" && !support)}>Save competence decision</button><button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => { setEditor(null); setSupport(null); }}>Cancel competence editing</button></div>
    </fieldset></form>}
    <details className="ncr-timeline" aria-busy={loading}><summary>Competence review history</summary>{loading ? <div className="related-capa-loading" role="status" aria-label="Loading competence history"><span aria-hidden="true" /></div> : history.length ? <ol className="related-capa-list">{history.map(row => <li key={row.id}><div><strong>Competence review {row.review_version} · {row.decision}</strong><span>{row.subject_name_snapshot} · {row.document_code_snapshot} · {row.document_revision_snapshot}</span><span className="ia-scope-summary">{row.notes}</span><small>{row.reviewer_name_snapshot} · Plan version {row.source_audit_version} · {new Date(row.created_at).toLocaleString()}</small></div></li>)}</ol> : <p className="qms-history-caption">No recorded competence assessments on this page.</p>}
      <div className="ia-pagination"><button type="button" className="secondary-action compact-action" disabled={!!editor || loading || busy || disabled || !historyOffset} onClick={() => setHistoryOffset(value => Math.max(0, value - 20))}>Previous competence reviews</button><span>Page {historyOffset / 20 + 1}</span><button type="button" className="secondary-action compact-action" disabled={!!editor || loading || busy || disabled || !nextHistory} onClick={() => setHistoryOffset(value => value + 20)}>More competence reviews</button></div>
    </details>
  </section>;
}
