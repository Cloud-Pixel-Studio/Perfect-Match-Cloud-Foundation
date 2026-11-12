"use client";

import { ArrowRight, ClipboardCheck, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

type Origin = {
  kind: "ncr" | "risk";
  id: string;
  unit_id: string;
  process_id: string;
  code: string;
  name: string;
  description: string;
  state: string;
  target_date?: string | null;
};
type RelatedCAPA = {
  id: string; unit_id: string; process_id: string; code: string; name: string; state: string;
  source_type: string; source_ncr_id: string | null; source_risk_id: string | null;
  target_date: string | null;
};
const api = "/api/identity";
const pageSize = 20;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function matches(value: RelatedCAPA, origin: Pick<Origin, "kind" | "id" | "unit_id">) {
  return value !== null && typeof value === "object" && typeof value.id === "string"
    && typeof value.code === "string" && typeof value.name === "string" && typeof value.state === "string"
    && uuid.test(value.id) && value.unit_id === origin.unit_id && value.source_type === origin.kind
    && (origin.kind === "ncr" ? value.source_ncr_id === origin.id && !value.source_risk_id : value.source_risk_id === origin.id && !value.source_ncr_id);
}
function href(row: RelatedCAPA) {
  return `/?${new URLSearchParams({ pm_source: "capa", pm_record: row.id, pm_unit: row.unit_id })}#capa-heading`;
}
function failure(status: number) {
  if (status === 401) return "Your session has expired. Sign in again.";
  if (status === 403) return "Corrective-action access is not permitted. Refresh your responsibilities.";
  if (status === 404) return "This source is unavailable with your current access. Refresh the source record.";
  if (status === 409) return "The CAPA code or source conflicts with the current record. Review the draft before trying again.";
  if (status === 422) return "Review the CAPA code, title, problem statement and date.";
  return "Corrective actions are temporarily unavailable. Try refreshing.";
}

export function RelatedCAPAs({ origin, capabilities, disabled = false, onBusyChange, onAccessChanged }: {
  origin: Origin; capabilities: string[]; disabled?: boolean;
  onBusyChange?: (busy: boolean) => void; onAccessChanged?: () => void;
}) {
  const heading = useId();
  const canRead = capabilities.includes("capa.read") && capabilities.includes(origin.kind === "ncr" ? "ncr.read" : "risks.read");
  const canCreate = canRead && capabilities.includes("capa.manage") && capabilities.includes("processes.read") && origin.state !== "cancelled";
  const [rows, setRows] = useState<RelatedCAPA[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [denied, setDenied] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [created, setCreated] = useState<RelatedCAPA | null>(null);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const epoch = useRef(0);
  const operation = useRef(0);
  const postBusy = useRef(false);
  const busyCallback = useRef(onBusyChange);
  const accessCallback = useRef(onAccessChanged);
  const source = useMemo(() => ({ kind: origin.kind, id: origin.id, unit_id: origin.unit_id }), [origin.kind, origin.id, origin.unit_id]);
  const context = `${origin.kind}:${origin.unit_id}:${origin.id}:${origin.process_id}:${canRead}:${canCreate}`;
  const contextRef = useRef(context);

  useEffect(() => { busyCallback.current = onBusyChange; accessCallback.current = onAccessChanged; }, [onBusyChange, onAccessChanged]);
  const invalidate = useCallback((status: number) => {
    ++epoch.current; ++operation.current;
    setRows([]); setHasNext(false); setCreated(null); setCreating(false); setDenied(true); setLoading(false); setNotice(""); setError(failure(status));
    postBusy.current = false; setPosting(false); busyCallback.current?.(false); accessCallback.current?.();
  }, []);

  useEffect(() => {
    contextRef.current = context;
    const generation = ++epoch.current;
    const controller = new AbortController();
    const current = () => !controller.signal.aborted && generation === epoch.current;
    const timer = window.setTimeout(() => {
      setRows([]); setHasNext(false);
      if (!canRead || denied) { setLoading(false); return; }
      setLoading(true); setError("");
      const query = new URLSearchParams({ unit_id: source.unit_id, [source.kind === "ncr" ? "source_ncr_id" : "source_risk_id"]: source.id, limit: String(pageSize + 1), offset: String(offset) });
      void fetch(`${api}/capas?${query}`, { credentials: "include", signal: controller.signal })
        .then(async (response) => {
          if (!current()) return;
          if (!response.ok) {
            if ([401, 403, 404].includes(response.status)) { invalidate(response.status); return; }
            throw new Error(failure(response.status));
          }
          const data = await response.json() as RelatedCAPA[];
          if (!current()) return;
          if (!Array.isArray(data) || data.some((row) => !matches(row, source))) throw new Error("The related actions did not match this source. Refresh to verify the record.");
          setRows(data.slice(0, pageSize)); setHasNext(data.length > pageSize);
        })
        .catch((cause) => { if (current()) setError(cause instanceof Error ? cause.message : failure(503)); })
        .finally(() => { if (current()) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [context, source, canRead, denied, offset, refresh, invalidate]);

  useEffect(() => {
    const mutationEpoch = operation;
    const pending = postBusy;
    const onBusy = busyCallback;
    const timer = window.setTimeout(() => { setCreating(false); setCreated(null); setNotice(""); setPosting(false); setUnconfirmed(false); }, 0);
    return () => {
      window.clearTimeout(timer); ++mutationEpoch.current;
      if (pending.current) onBusy.current?.(false);
      pending.current = false;
    };
  }, [context]);

  useEffect(() => {
    const requestEpoch = epoch;
    const mutationEpoch = operation;
    const pending = postBusy;
    const onBusy = busyCallback;
    return () => {
      ++requestEpoch.current; ++mutationEpoch.current;
      if (pending.current) onBusy.current?.(false);
    };
  }, []);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate || disabled || denied || unconfirmed || postBusy.current) return;
    const data = new FormData(event.currentTarget);
    const code = String(data.get("code") ?? "").trim();
    const name = String(data.get("name") ?? "").trim();
    const problem = String(data.get("problem_statement") ?? "").trim();
    if (!code || !name || !problem) { setError("Enter a CAPA code, title and problem statement."); return; }
    const token = ++operation.current;
    const source = context;
    const current = () => operation.current === token && contextRef.current === source;
    postBusy.current = true; setPosting(true); busyCallback.current?.(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const csrf = cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
      const response = await fetch(`${api}/capas`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify({
        unit_id: origin.unit_id, process_id: origin.process_id, code, name,
        source_type: origin.kind, source_ncr_id: origin.kind === "ncr" ? origin.id : null,
        source_risk_id: origin.kind === "risk" ? origin.id : null, source_reference: origin.code,
        problem_statement: problem, owner_user_id: null, target_date: data.get("target_date") || null, root_cause_method: null,
      }) });
      if (!current()) return;
      if (!response.ok) {
        if ([401, 403, 404].includes(response.status)) { invalidate(response.status); return; }
        throw new Error(failure(response.status));
      }
      if (response.status !== 201) { setUnconfirmed(true); throw new Error("The creation outcome could not be confirmed. Refresh the register and review existing CAPA before creating another."); }
      // A successful HTTP status can still carry an invalid response. Keep the
      // draft visible, but do not permit a second write with an uncertain result.
      setUnconfirmed(true);
      const row = await response.json() as RelatedCAPA;
      if (!current()) return;
      if (!matches(row, origin) || row.process_id !== origin.process_id) throw new Error("The creation response could not be verified. Refresh before trying another creation.");
      setUnconfirmed(false); setCreated(row); setCreating(false); setNotice(`CAPA ${row.code} was created. Open it to assign responsibilities and plan actions.`);
      setOffset(0); setRefresh((value) => value + 1);
    } catch (cause) { if (current()) setError(cause instanceof Error ? cause.message : failure(503)); }
    finally { if (current()) { postBusy.current = false; setPosting(false); busyCallback.current?.(false); } }
  }

  if (!canRead && !denied) return null;
  return <section className="related-capas ncr-read-section" aria-labelledby={heading} aria-busy={loading || posting}>
    <div className="related-capas-heading"><div><h4 id={heading}><ClipboardCheck aria-hidden="true" size={18} />Corrective actions from this record</h4><p>Actions linked to {origin.code}. Creating a CAPA preserves this source and its process.</p></div><button type="button" className="icon-button" aria-label="Refresh related CAPA" disabled={posting || disabled} onClick={() => { setDenied(false); setOffset(0); setRefresh((value) => value + 1); }}><RefreshCw aria-hidden="true" size={17} /></button></div>
    {error && <p role="alert" className="denied-state">{error}</p>}
    {notice && <p role="status" className="workflow-message">{notice}</p>}
    {unconfirmed && <p role="status" className="qms-history-caption">Creation outcome is unconfirmed. Refresh the nonconformity or risk register and review existing CAPA before creating another. This draft cannot be resubmitted.</p>}
    {created && !denied && <a className="related-capa-created" href={href(created)}>Open CAPA {created.code}<ArrowRight aria-hidden="true" size={15} /></a>}
    {loading ? <div className="related-capa-loading" role="status" aria-label="Loading related corrective actions"><span aria-hidden="true" /><span aria-hidden="true" /></div> : !error && !denied && (rows.length ? <ul className="related-capa-list">{rows.map((row) => <li key={row.id}><div><strong>{row.code}</strong><span>{row.name}</span><small>{row.state.replaceAll("_", " ")}{row.target_date ? ` · Due ${row.target_date}` : ""}</small></div><a href={href(row)} aria-label={`Open CAPA ${row.code}`}><ArrowRight aria-hidden="true" size={17} /><span>Open</span></a></li>)}</ul> : <p className="qms-history-caption">No corrective actions are linked to this record yet.</p>)}
    {!denied && (offset > 0 || hasNext) && <nav className="related-capa-pages" aria-label="Related CAPA pages"><button type="button" className="secondary-action compact-action" disabled={loading || posting || disabled || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous actions</button><span>Showing {rows.length ? offset + 1 : 0}–{offset + rows.length}</span><button type="button" className="secondary-action compact-action" disabled={loading || posting || disabled || !hasNext || offset + pageSize > 1_000_000} onClick={() => setOffset(offset + pageSize)}>More actions</button></nav>}
    {canCreate && !denied && !creating && <button type="button" className="secondary-action compact-action" disabled={disabled || posting || loading} onClick={() => { setCreating(true); setError(""); }}><Plus aria-hidden="true" size={16} />Create CAPA</button>}
    {origin.state === "cancelled" && <p className="qms-history-caption">This source is cancelled. Existing CAPA remain available for traceability.</p>}
    {creating && canCreate && !denied && <form className="ncr-editor related-capa-form" aria-label="Create corrective action" onSubmit={(event) => void create(event)}><p className="qms-history-caption">Source: {origin.code} · {origin.kind === "ncr" ? "Nonconformity" : "Risk or opportunity"}. The source and process are fixed. Assign the responsible person in the CAPA workspace.</p><fieldset disabled={posting || disabled}><div className="ncr-form-grid"><label>CAPA code<input name="code" maxLength={40} required /></label><label>CAPA title<input name="name" maxLength={160} defaultValue={origin.name} required /></label><label className="ncr-wide">Problem statement<textarea name="problem_statement" maxLength={4000} rows={3} defaultValue={origin.description} required /></label><label>Target date<input name="target_date" type="date" defaultValue={origin.target_date ?? ""} /></label></div><div className="ncr-form-actions"><button type="submit" disabled={unconfirmed} className="primary-action compact-action">{posting ? "Creating CAPA…" : "Create corrective action"}</button><button type="button" className="secondary-action compact-action" onClick={() => setCreating(false)}>Cancel CAPA</button></div></fieldset></form>}
  </section>;
}
