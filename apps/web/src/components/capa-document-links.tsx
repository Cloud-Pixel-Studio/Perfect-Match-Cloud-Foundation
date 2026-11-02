"use client";

import { Link2, Plus, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type CAPAScope = { id: string; unit_id: string; row_version: number; state: string };
type Link = { id: string; status: "active" | "removed"; row_version: number;
  snapshot_code: string; snapshot_name: string; snapshot_revision: string;
  target_state: string; created_at: string; removed_at: string | null; removal_reason: string };
type Candidate = { id: string; code: string; title: string; status: string };
type Revision = { id: string; revision: string; status: string; file_state: string };
const api = "/api/identity";
const pageSize = 50;

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as T;
}

function failure(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : "";
  if (["401", "403"].includes(code)) return "Your access changed. Refresh permissions before continuing.";
  if (code === "404") return "The CAPA or document is no longer available with your access.";
  if (code === "409") return "The CAPA, document or link changed. Refresh and review the latest version.";
  if (code === "422") return "Select a released document revision or enter a removal reason.";
  return "Related documents could not be reached. Try refreshing.";
}

export function CAPADocumentLinks({ capa, canRead, canManage, disabled, onChanged, onAccessChanged }: {
  capa: CAPAScope; canRead: boolean; canManage: boolean; disabled: boolean;
  onChanged: () => void; onAccessChanged: () => void;
}) {
  const [links, setLinks] = useState<Link[]>([]);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState({ search: "", offset: 0 });
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogHasNext, setCatalogHasNext] = useState(false);
  const [documentId, setDocumentId] = useState("");
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [revisionId, setRevisionId] = useState("");
  const [revisionLoading, setRevisionLoading] = useState(false);
  const [removing, setRemoving] = useState<Link | null>(null);
  const [reason, setReason] = useState("");
  const scope = useRef(0);
  const canWrite = canRead && canManage && ["draft", "analysis", "action_planned", "implementation"].includes(capa.state);

  useEffect(() => { const epoch = scope; ++epoch.current; return () => { ++epoch.current; }; }, [capa.id, capa.unit_id]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      if (!canRead) { setLinks([]); setLoading(false); return; }
      setLoading(true); setLoadError("");
      void read<Link[]>(`/capas/${capa.id}/document-links?limit=${pageSize}&offset=${offset}`, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setLinks(data); })
        .catch((cause) => { if (!controller.signal.aborted) { setLinks([]); setLoadError(failure(cause)); if (cause instanceof Error && ["401", "403"].includes(cause.message)) onAccessChanged(); } })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [capa.id, capa.row_version, canRead, offset, reload, onAccessChanged]);

  useEffect(() => {
    const controller = new AbortController();
    if (!adding || !canWrite) return () => controller.abort();
    const params = new URLSearchParams({ unit_id: capa.unit_id, search: query.search, limit: String(pageSize), offset: String(query.offset) });
    const timer = window.setTimeout(() => {
      setCatalogLoading(true);
      void read<Candidate[]>(`/documents?${params}`, controller.signal)
        .then((data) => { if (!controller.signal.aborted) { setCatalogHasNext(data.length === pageSize); setCandidates(data.filter((item) => item.status === "active")); } })
        .catch((cause) => { if (!controller.signal.aborted) { setCandidates([]); setCatalogHasNext(false); setError(failure(cause)); } })
        .finally(() => { if (!controller.signal.aborted) setCatalogLoading(false); });
    }, 150);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [adding, canWrite, capa.unit_id, query]);

  useEffect(() => {
    const controller = new AbortController();
    if (!documentId || !adding || !canWrite) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setRevisionLoading(true);
      void read<Revision[]>(`/documents/${documentId}/revisions`, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setRevisions(data.filter((item) => item.status === "active" && item.file_state === "clean")); })
        .catch((cause) => { if (!controller.signal.aborted) setError(failure(cause)); })
        .finally(() => { if (!controller.signal.aborted) setRevisionLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [documentId, adding, canWrite]);

  async function mutate(body: object, link?: Link) {
    if (busy || disabled || !canWrite) return;
    const epoch = scope.current;
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${capa.id}/document-links${link ? `/${link.id}/remove` : ""}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(String(response.status));
      if (epoch !== scope.current) return;
      setAdding(false); setRemoving(null); setReason(""); setDocumentId(""); setRevisionId("");
      setNotice(link ? "Document reference removed; its history remains available." : "Released revision linked to this CAPA.");
      setReload((value) => value + 1); onChanged();
    } catch (cause) {
      if (epoch !== scope.current) return;
      setError(failure(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) onAccessChanged();
    } finally { if (epoch === scope.current) setBusy(false); }
  }

  return <section className="ncr-editor" aria-label="CAPA controlled document references" aria-busy={loading || busy}>
    <div className="ncr-detail-heading"><div><p className="eyebrow">Traceability</p><h4><Link2 size={17} aria-hidden="true" /> Controlled documents</h4></div><div className="ncr-form-actions"><button className="secondary-action compact-action" type="button" disabled={disabled || busy} onClick={() => setReload((value) => value + 1)} aria-label="Refresh CAPA document links"><RefreshCw size={15} aria-hidden="true" /></button>{canWrite && <button className="secondary-action compact-action" type="button" disabled={disabled || busy} onClick={() => { setAdding((value) => !value); setError(""); }}><Plus size={15} aria-hidden="true" /> Link document</button>}</div></div>
    <p className="qms-history-caption">Cite a clean, released revision. References are locked when effectiveness review begins.</p>
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {adding && canWrite && <form className="ncr-editor" onSubmit={(event) => { event.preventDefault(); if (documentId && revisionId) void mutate({ expected_version: capa.row_version, document_id: documentId, document_revision_id: revisionId }); }}><fieldset disabled={busy || disabled}><label>Search documents<input value={search} maxLength={160} onChange={(event) => { setSearch(event.target.value); setQuery({ search: event.target.value.trim(), offset: 0 }); }} /></label><label>Document<select value={documentId} onChange={(event) => { setDocumentId(event.target.value); setRevisionId(""); setRevisions([]); }} disabled={catalogLoading}><option value="">Select a document</option>{candidates.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.title}</option>)}</select></label><div className="ncr-pagination"><button type="button" disabled={query.offset === 0 || catalogLoading} onClick={() => setQuery({ ...query, offset: Math.max(0, query.offset - pageSize) })}>Previous</button><span>Page {Math.floor(query.offset / pageSize) + 1}</span><button type="button" disabled={!catalogHasNext || catalogLoading} onClick={() => setQuery({ ...query, offset: query.offset + pageSize })}>Next</button></div><label>Released revision<select value={revisionId} onChange={(event) => setRevisionId(event.target.value)} disabled={!documentId || revisionLoading}><option value="">Select a clean revision</option>{revisions.map((item) => <option key={item.id} value={item.id}>{item.revision}</option>)}</select></label>{documentId && !revisionLoading && !revisions.length && <p className="qms-history-caption">This document has no clean released revision.</p>}<div className="ncr-form-actions"><button className="primary-action compact-action" type="submit" disabled={!documentId || !revisionId}>Link revision</button><button className="secondary-action compact-action" type="button" onClick={() => setAdding(false)}>Cancel</button></div></fieldset></form>}
    {loading ? <RecordWorkspaceSkeleton label="Loading controlled document references" /> : loadError ? <div className="ncr-empty" role="alert"><strong>Document links could not load</strong><p>{loadError}</p><button className="secondary-action compact-action" type="button" onClick={() => setReload((value) => value + 1)}>Retry</button></div> : links.length ? <ul className="ncr-record-list">{links.map((item) => <li key={item.id}><div className="ncr-list-heading"><strong>{item.snapshot_code} · revision {item.snapshot_revision}</strong><span className="process-status">{item.status}</span></div><p>{item.snapshot_name}</p><small>Current status: {item.target_state.replaceAll("_", " ")} · linked {new Date(item.created_at).toLocaleDateString()}</small>{item.status === "removed" && <small>Removed {item.removed_at ? new Date(item.removed_at).toLocaleDateString() : ""} · {item.removal_reason}</small>}{canWrite && item.status === "active" && <button className="secondary-action compact-action" type="button" disabled={busy || disabled} onClick={() => { setRemoving(item); setReason(""); }}>Remove reference</button>}{removing?.id === item.id && <form onSubmit={(event) => { event.preventDefault(); if (reason.trim()) void mutate({ expected_version: capa.row_version, expected_link_version: item.row_version, reason: reason.trim() }, item); }}><label>Reason for removal<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} required /></label><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit" disabled={busy || !reason.trim()}>Confirm removal</button><button className="secondary-action compact-action" type="button" onClick={() => setRemoving(null)}>Cancel</button></div></form>}</li>)}</ul> : <p className="ncr-empty">No document revisions linked to this CAPA.</p>}
    <nav className="ncr-pagination" aria-label="CAPA document link pages"><button type="button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button><span>Page {Math.floor(offset / pageSize) + 1}</span><button type="button" disabled={loading || !!loadError || links.length < pageSize} onClick={() => setOffset(offset + pageSize)}>Next</button></nav>
  </section>;
}
