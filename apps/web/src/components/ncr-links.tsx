"use client";

import { Link2, Plus, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type NCRScope = { id: string; unit_id: string; row_version: number; state: string };
type Kind = "risk" | "control" | "document" | "evidence";
type RelatedLink = {
  id: string; nonconformity_id: string; unit_id: string; status: "active" | "removed";
  row_version: number; ncr_row_version: number; snapshot_code: string; snapshot_name: string;
  linked_target_version: number; target_state: string; created_at: string;
  removed_at: string | null; removal_reason: string; snapshot_revision?: string;
};
type Candidate = { id: string; code: string; name?: string; title?: string; status?: string; state?: string };
type Revision = { id: string; revision: string; status: string; file_state: string };
type ReviewedEvidence = { id: string; name: string; status: string; row_version: number };
type Choice = { id: string; name: string };
type Callbacks = {
  onVersionChange: (version: number) => void;
  onBusyChange: (busy: boolean) => void;
  onAccessChanged: () => void;
};
const api = "/api/identity";
const pageSize = 50;
const titles: Record<Kind, string> = { risk: "Risks and opportunities", control: "Control implementations", document: "Controlled document revisions", evidence: "Accepted implementation evidence" };
const capabilities: Record<Kind, string> = { risk: "risks.read", control: "control_instances.read", document: "documents.read", evidence: "control_instances.read" };
const label = (value: string) => value.replaceAll("_", " ");
const dateLabel = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
const terminal = (state: string) => state === "closed" || state === "cancelled";
const candidateName = (item: Candidate) => `${item.code} · ${item.name ?? item.title ?? "Related record"}`;

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as T;
}

function failure(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : "";
  if (["401", "403"].includes(code)) return "Your access changed. Refresh the nonconformity permissions before continuing.";
  if (code === "404") return "The nonconformity or related record is no longer available with your access.";
  if (code === "409") return "The record or link changed. Refresh and review the latest version before trying again.";
  if (code === "422") return "Choose an available record and provide the required explanation.";
  return "Related records could not be reached. Refresh and try again.";
}
const accessDenied = (cause: unknown) => cause instanceof Error && ["401", "403"].includes(cause.message);

function NCRLinkGroup({ kind, ncr, canRead, canManage, disabled, callbacks, mutationBusyRef }: {
  kind: Kind; ncr: NCRScope; canRead: boolean; canManage: boolean; disabled: boolean;
  callbacks: Callbacks; mutationBusyRef: React.RefObject<boolean>;
}) {
  const [links, setLinks] = useState<RelatedLink[]>([]);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);
  const [removal, setRemoval] = useState<{ id: string; reason: string } | null>(null);
  const [query, setQuery] = useState({ search: "", offset: 0 });
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [choice, setChoice] = useState<Choice>({ id: "", name: "" });
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [revisionId, setRevisionId] = useState("");
  const [revisionBusy, setRevisionBusy] = useState(false);
  const [revisionError, setRevisionError] = useState("");
  const [evidenceItems, setEvidenceItems] = useState<ReviewedEvidence[]>([]);
  const [evidenceId, setEvidenceId] = useState("");
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");
  const scopeEpoch = useRef(0);
  const linkRequest = useRef(0);
  const catalogRequest = useRef(0);
  const revisionRequest = useRef(0);
  const callbackRef = useRef(callbacks);
  const canWrite = canRead && canManage && !terminal(ncr.state);
  const base = `/nonconformities/${ncr.id}/${kind}-links`;

  useEffect(() => { callbackRef.current = callbacks; }, [callbacks]);
  useEffect(() => {
    const epoch = scopeEpoch;
    ++epoch.current;
    return () => { ++epoch.current; };
  }, [ncr.id, ncr.unit_id, canRead, canManage]);

  useEffect(() => {
    const controller = new AbortController();
    const request = ++linkRequest.current;
    const timer = window.setTimeout(() => {
      setLoading(true); setLoadError("");
      if (!canRead) {
        setLinks([]); setCandidates([]); setChoice({ id: "", name: "" }); setRevisions([]); setRevisionId("");
        setAdding(false); setRemoval(null); setLoading(false); return;
      }
      void read<RelatedLink[]>(`${base}?limit=${pageSize}&offset=${offset}`, controller.signal).then((data) => {
        if (!controller.signal.aborted && request === linkRequest.current) setLinks(data);
      }).catch((cause) => {
        if (controller.signal.aborted || request !== linkRequest.current) return;
        setLinks([]); setLoadError(failure(cause)); setAdding(false); setRemoval(null);
        if (accessDenied(cause)) {
          setCandidates([]); setChoice({ id: "", name: "" }); setRevisions([]); setRevisionId("");
          callbackRef.current.onAccessChanged();
        }
      }).finally(() => { if (!controller.signal.aborted && request === linkRequest.current) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [base, canRead, ncr.row_version, offset, refresh]);

  useEffect(() => {
    const controller = new AbortController();
    const request = ++catalogRequest.current;
    if (!adding || !canWrite) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setCatalogBusy(true); setCatalogError("");
      const params = new URLSearchParams({ unit_id: ncr.unit_id, limit: String(pageSize), offset: String(query.offset) });
      params.set(kind === "risk" ? "q" : "search", query.search);
      const endpoint = kind === "risk" ? "risks" : kind === "document" ? "documents" : "control-instances";
      void read<Candidate[]>(`/${endpoint}?${params}`, controller.signal).then((data) => {
        if (!controller.signal.aborted && request === catalogRequest.current) setCandidates(data);
      }).catch((cause) => {
        if (controller.signal.aborted || request !== catalogRequest.current) return;
        setCandidates([]); setCatalogError(failure(cause));
        if (accessDenied(cause)) {
          setLinks([]); setChoice({ id: "", name: "" }); setRevisions([]); setRevisionId(""); setAdding(false);
          callbackRef.current.onAccessChanged();
        }
      }).finally(() => { if (!controller.signal.aborted && request === catalogRequest.current) setCatalogBusy(false); });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [kind, ncr.unit_id, adding, canWrite, query]);

  useEffect(() => {
    const controller = new AbortController();
    const request = ++revisionRequest.current;
    if (kind !== "document" || !choice.id || !adding || !canWrite) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setRevisionBusy(true); setRevisionError("");
      void read<Revision[]>(`/documents/${choice.id}/revisions`, controller.signal).then((data) => {
        if (!controller.signal.aborted && request === revisionRequest.current) setRevisions(data.filter((item) => item.status === "active" && item.file_state === "clean"));
      }).catch((cause) => {
        if (controller.signal.aborted || request !== revisionRequest.current) return;
        setRevisions([]); setRevisionId(""); setRevisionError(failure(cause));
        if (accessDenied(cause)) { setLinks([]); setCandidates([]); setChoice({ id: "", name: "" }); setAdding(false); callbackRef.current.onAccessChanged(); }
      }).finally(() => { if (!controller.signal.aborted && request === revisionRequest.current) setRevisionBusy(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [kind, choice.id, adding, canWrite]);

  useEffect(() => {
    const controller = new AbortController();
    if (kind !== "evidence" || !choice.id || !adding || !canWrite) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setEvidenceBusy(true); setEvidenceError(""); setEvidenceItems([]); setEvidenceId("");
      void read<ReviewedEvidence[]>(`/control-instance-evidence?instance_id=${choice.id}&limit=200`, controller.signal).then((data) => {
        if (!controller.signal.aborted) setEvidenceItems(data.filter((item) => item.status === "accepted"));
      }).catch((cause) => {
        if (controller.signal.aborted) return;
        setEvidenceError(failure(cause)); setEvidenceItems([]); setEvidenceId("");
        if (accessDenied(cause)) { setLinks([]); setCandidates([]); setChoice({ id: "", name: "" }); setAdding(false); callbackRef.current.onAccessChanged(); }
      }).finally(() => { if (!controller.signal.aborted) setEvidenceBusy(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [kind, choice.id, adding, canWrite]);

  async function mutate(body: object, link?: RelatedLink) {
    if (disabled || mutationBusyRef.current || !canWrite) return;
    mutationBusyRef.current = true;
    const epoch = scopeEpoch.current;
    callbackRef.current.onBusyChange(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}${base}${link ? `/${link.id}/remove` : ""}`, {
        method: "POST", credentials: "include", headers: {
          "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "",
        }, body: JSON.stringify(body),
      });
      if (epoch !== scopeEpoch.current) return;
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json() as RelatedLink;
      if (epoch !== scopeEpoch.current) return;
      setAdding(false); setRemoval(null);
      setNotice(link ? "Link removed. Its reference and removal reason remain in the history." : "Record linked. Its reference has been preserved.");
      callbackRef.current.onVersionChange(result.ncr_row_version);
      // Refresh also covers a successful response when the parent version was already refreshed elsewhere.
      setRefresh((value) => value + 1);
    } catch (cause) {
      if (epoch !== scopeEpoch.current) return;
      setError(failure(cause));
      if (accessDenied(cause)) {
        setLinks([]); setCandidates([]); setChoice({ id: "", name: "" }); setRevisions([]); setRevisionId("");
        setAdding(false); setRemoval(null); setLoadError(failure(cause)); callbackRef.current.onAccessChanged();
      }
    } finally {
      mutationBusyRef.current = false;
      callbackRef.current.onBusyChange(false);
    }
  }

  function linkItem(item: RelatedLink) {
    const removing = canWrite && removal?.id === item.id;
    return <li key={item.id} className={item.status === "removed" ? "risk-link-removed" : undefined}>
      <div className="risk-link-heading"><strong>{item.snapshot_code}{item.snapshot_revision ? ` · ${item.snapshot_revision}` : ""}</strong><span className={`qms-grant-status ${item.status === "active" ? "assigned" : "revoked"}`}>{item.status === "active" ? "Linked" : "Removed"}</span></div>
      <p>{item.snapshot_name}</p>
      <small>Linked {dateLabel(item.created_at)} · {kind === "document" ? "Released revision" : `Reference version ${item.linked_target_version}`} · Current status: {label(item.target_state)}</small>
      {item.status === "removed" && <p>Removed {item.removed_at ? dateLabel(item.removed_at) : ""}: {item.removal_reason}</p>}
      {canWrite && item.status === "active" && !removing && <button className="secondary-action compact-action" type="button" disabled={disabled || loading} onClick={() => { setRemoval({ id: item.id, reason: "" }); setAdding(false); }}>Remove link</button>}
      {removing && <form className="risk-link-removal" onSubmit={(event) => {
        event.preventDefault(); if (!removal.reason.trim()) return;
        void mutate({ expected_version: ncr.row_version, expected_link_version: item.row_version, reason: removal.reason }, item);
      }}><label>Reason for removing this link<textarea rows={2} required maxLength={500} value={removal.reason} disabled={disabled} onChange={(event) => setRemoval({ id: item.id, reason: event.target.value })} /></label><div><button className="secondary-action compact-action" disabled={disabled || !removal.reason.trim()} type="submit">Confirm removal</button><button className="secondary-action compact-action" disabled={disabled} type="button" onClick={() => setRemoval(null)}>Keep link</button></div></form>}
    </li>;
  }

  const active = links.filter((item) => item.status === "active");
  const removed = links.filter((item) => item.status === "removed");
  const eligible = candidates.filter((item) => kind === "risk" || item.status === "active");
  const chosenOnPage = candidates.find((item) => item.id === choice.id);
  const choiceAvailable = !!choice.id && (!chosenOnPage || kind === "risk" || chosenOnPage.status === "active");
  return <section className="risk-link-group" aria-label={`Related ${titles[kind].toLowerCase()}`}>
    <div className="risk-link-group-heading"><h5>{titles[kind]}</h5>{canWrite && <button className="secondary-action compact-action" type="button" disabled={disabled || loading || !!loadError} onClick={() => {
      setAdding((value) => !value); setRemoval(null); setError(""); setNotice("");
    }}><Plus size={14} aria-hidden="true" /> Add link</button>}</div>
    {!canRead ? <p className="qms-history-caption">Read responsibility for {titles[kind].toLowerCase()} is required to view these related records.</p> : loadError ? <p className="denied-state" role="alert">{loadError}</p> : loading ? <p role="status">Loading related records…</p> : <>
      <ul className="risk-link-list">{active.map(linkItem)}</ul>
      {!active.length && <p className="qms-history-caption">No active links on this page.</p>}
      {!!removed.length && <details className="risk-link-history"><summary>Removed links on this page ({removed.length})</summary><ul className="risk-link-list">{removed.map(linkItem)}</ul></details>}
      <nav className="ncr-pagination" aria-label={`${titles[kind]} link pages`}><button type="button" disabled={disabled || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous links</button><span>Page {Math.floor(offset / pageSize) + 1}</span><button type="button" disabled={disabled || links.length < pageSize || offset >= 1_000_000} onClick={() => setOffset(offset + pageSize)}>Next links</button></nav>
    </>}
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {adding && canWrite && !loadError && <form className="risk-link-editor" onSubmit={(event) => {
      event.preventDefault(); if (!choiceAvailable || (kind === "document" && !revisionId) || (kind === "evidence" && !evidenceId)) return;
      const target = kind === "risk" ? { risk_id: choice.id } : kind === "control" ? { control_instance_id: choice.id } : kind === "evidence" ? { evidence_id: evidenceId } : { document_id: choice.id, document_revision_id: revisionId };
      void mutate({ expected_version: ncr.row_version, ...target });
    }}><fieldset disabled={disabled}>
      <label>Find by code or title<input maxLength={160} value={query.search} onChange={(event) => setQuery({ search: event.target.value, offset: 0 })} /></label>
      {catalogBusy && <p role="status">Loading available records…</p>}
      {catalogError && <p className="denied-state" role="alert">{catalogError}</p>}
      <label>{kind === "risk" ? "Risk or opportunity" : kind === "document" ? "Active controlled document" : "Active implementation"}<select required value={choice.id} disabled={catalogBusy || !!catalogError} onChange={(event) => {
        const chosen = eligible.find((item) => item.id === event.target.value);
        setChoice({ id: event.target.value, name: chosen ? candidateName(chosen) : "" });
        setRevisionId(""); setRevisions([]); setRevisionError("");
        setEvidenceId(""); setEvidenceItems([]); setEvidenceError("");
      }}><option value="">Select a record</option>
        {choice.id && !eligible.some((item) => item.id === choice.id) && <option value={choice.id} disabled={!choiceAvailable}>{choice.name}{choiceAvailable ? "" : " · No longer active"}</option>}
        {eligible.map((item) => <option key={item.id} value={item.id}>{candidateName(item)}{kind === "risk" && item.state ? ` · ${label(item.state)}` : ""}</option>)}
      </select></label>
      {kind === "document" && <>
        <label>Released revision<select required value={revisionId} disabled={revisionBusy || !choiceAvailable || !!revisionError} onChange={(event) => setRevisionId(event.target.value)}><option value="">Select a released revision</option>{revisions.map((item) => <option key={item.id} value={item.id}>{item.revision}</option>)}</select></label>
        {revisionBusy && <p role="status">Loading released revisions…</p>}{revisionError && <p className="denied-state" role="alert">{revisionError}</p>}
        {choiceAvailable && !revisionBusy && !revisionError && !revisions.length && <p className="qms-history-caption">No released, clean revision is currently available for this document.</p>}
      </>}
      {kind === "evidence" && <>
        <label>Accepted evidence<select required value={evidenceId} disabled={evidenceBusy || !choiceAvailable || !!evidenceError} onChange={(event) => setEvidenceId(event.target.value)}><option value="">Select accepted evidence</option>{evidenceItems.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        {evidenceBusy && <p role="status">Loading reviewed evidence…</p>}{evidenceError && <p className="denied-state" role="alert">{evidenceError}</p>}
        {choiceAvailable && !evidenceBusy && !evidenceError && !evidenceItems.length && <p className="qms-history-caption">No accepted evidence is currently available on this implementation.</p>}
      </>}
      <nav className="ncr-pagination" aria-label={`${titles[kind]} selection pages`}><button type="button" disabled={catalogBusy || query.offset === 0} onClick={() => setQuery((value) => ({ ...value, offset: Math.max(0, value.offset - pageSize) }))}>Previous results</button><span>Page {Math.floor(query.offset / pageSize) + 1}</span><button type="button" disabled={catalogBusy || candidates.length < pageSize || query.offset >= 1_000_000} onClick={() => setQuery((value) => ({ ...value, offset: value.offset + pageSize }))}>More results</button></nav>
      <div className="risk-link-editor-actions"><button className="primary-action compact-action" type="submit" disabled={loading || catalogBusy || revisionBusy || evidenceBusy || !!catalogError || !!revisionError || !!evidenceError || !choiceAvailable || (kind === "document" && !revisionId) || (kind === "evidence" && !evidenceId)}>Link record</button><button className="secondary-action compact-action" type="button" onClick={() => setAdding(false)}>Cancel</button></div>
    </fieldset></form>}
  </section>;
}

export function NCRLinks({ ncr, capabilities: grants, disabled = false, onVersionChange, onBusyChange, onAccessChanged, onRefresh }: {
  ncr: NCRScope; capabilities: string[]; disabled?: boolean; onRefresh: () => void;
} & Callbacks) {
  const mutationBusyRef = useRef(false);
  const canRead = grants.includes("ncr.read");
  const canManage = canRead && grants.includes("ncr.manage");
  return <section className="risk-links" aria-labelledby={`ncr-links-${ncr.id}`}>
    <div className="risk-link-group-heading"><h4 id={`ncr-links-${ncr.id}`}><Link2 size={17} aria-hidden="true" /> Related records</h4><button className="secondary-action compact-action" type="button" disabled={disabled} onClick={onRefresh}><RefreshCw size={14} aria-hidden="true" /> Refresh links</button></div>
    <p className="qms-history-caption">Preserve references to risks, control implementations, accepted evidence and released documents in this organization scope. Later changes to a related record do not replace the saved reference.</p>
    {(["risk", "control", "evidence", "document"] as const).map((kind) => <NCRLinkGroup key={`${ncr.id}-${kind}`} kind={kind} ncr={ncr} canRead={canRead && grants.includes(capabilities[kind])} canManage={canManage} disabled={disabled} mutationBusyRef={mutationBusyRef} callbacks={{ onVersionChange, onBusyChange, onAccessChanged }} />)}
    {terminal(ncr.state) && <p className="qms-history-caption">Related records are read-only because this nonconformity is {ncr.state}.</p>}
  </section>;
}
