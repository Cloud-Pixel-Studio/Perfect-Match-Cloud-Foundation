"use client";

import { Link2, Plus, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type RiskScope = { id: string; unit_id: string; row_version: number; state: string };
type LinkKind = "control" | "document";
type RiskLink = {
  id: string; risk_id: string; unit_id: string; status: "active" | "removed";
  row_version: number; risk_row_version: number; snapshot_code: string; snapshot_name: string;
  linked_target_version: number; target_state: string; created_at: string;
  removed_at: string | null; removal_reason: string; snapshot_revision?: string;
};
type Control = { id: string; code: string; name: string; status: string };
type ControlledDocument = { id: string; code: string; title: string; status: string };
type Revision = { id: string; revision: string; status: string; file_state: string };
const api = "/api/identity";
const pageSize = 50;
const label = (value: string) => value.replaceAll("_", " ");
const dateLabel = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
const route = (kind: LinkKind) => `${kind}-links`;

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as T;
}

function failure(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : "";
  if (["401", "403"].includes(code)) return "Your access changed. Refresh the risk permissions before continuing.";
  if (code === "404") return "The risk or linked record is no longer available with your access.";
  if (code === "409") return "The risk, link or selected record changed. Refresh and review the latest version.";
  if (code === "422") return "Choose an available record and provide the required explanation.";
  return "Related records could not be reached. Refresh and try again.";
}

export function RiskLinks({ risk, capabilities, disabled = false, onVersionChange, onBusyChange, onRefresh }: {
  risk: RiskScope; capabilities: string[]; disabled?: boolean;
  onVersionChange: (version: number) => void; onBusyChange?: (busy: boolean) => void;
  onRefresh: () => void;
}) {
  const canManage = capabilities.includes("risks.manage") && risk.state !== "closed";
  const canReadControls = capabilities.includes("control_instances.read");
  const canReadDocuments = capabilities.includes("documents.read");
  const [controlLinks, setControlLinks] = useState<RiskLink[]>([]);
  const [documentLinks, setDocumentLinks] = useState<RiskLink[]>([]);
  const [linkPages, setLinkPages] = useState({ control: 0, document: 0 });
  const [loading, setLoading] = useState(true);
  const [controlError, setControlError] = useState("");
  const [documentError, setDocumentError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [addKind, setAddKind] = useState<LinkKind | null>(null);
  const [controls, setControls] = useState<Control[]>([]);
  const [documents, setDocuments] = useState<ControlledDocument[]>([]);
  const [controlQuery, setControlQuery] = useState({ search: "", offset: 0 });
  const [documentQuery, setDocumentQuery] = useState({ search: "", offset: 0 });
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [controlChoice, setControlChoice] = useState({ id: "", name: "" });
  const [documentChoice, setDocumentChoice] = useState({ id: "", name: "" });
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [revisionId, setRevisionId] = useState("");
  const [revisionBusy, setRevisionBusy] = useState(false);
  const [removal, setRemoval] = useState<{ kind: LinkKind; id: string; reason: string } | null>(null);
  const epoch = useRef(0);
  const mutation = useRef(0);
  const mutationBusy = useRef(false);

  useEffect(() => {
    const scopeEpoch = epoch;
    const mutationEpoch = mutation;
    return () => { ++scopeEpoch.current; ++mutationEpoch.current; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const revision = ++epoch.current;
    const timer = window.setTimeout(() => {
      setLoading(true); setControlError(""); setDocumentError("");
      const loadKind = async (kind: LinkKind, allowed: boolean) => {
        if (!allowed) return [];
        try {
          return await read<RiskLink[]>(`/risks/${risk.id}/${route(kind)}?limit=${pageSize}&offset=${linkPages[kind]}`, controller.signal);
        } catch (cause) {
          if (revision === epoch.current && !controller.signal.aborted) {
            if (kind === "control") setControlError(failure(cause));
            else setDocumentError(failure(cause));
          }
          return [];
        }
      };
      void Promise.all([loadKind("control", canReadControls), loadKind("document", canReadDocuments)]).then(([nextControls, nextDocuments]) => {
        if (revision !== epoch.current || controller.signal.aborted) return;
        setControlLinks(nextControls); setDocumentLinks(nextDocuments); setLoading(false);
      });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [risk.id, risk.row_version, canReadControls, canReadDocuments, linkPages]);

  useEffect(() => {
    const controller = new AbortController();
    if (!canManage || !addKind || (addKind === "control" ? !canReadControls : !canReadDocuments)) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setCatalogBusy(true); setError("");
      const query = addKind === "control" ? controlQuery : documentQuery;
      const params = new URLSearchParams({ unit_id: risk.unit_id, search: query.search, offset: String(query.offset), limit: String(pageSize) });
      if (addKind === "control") {
        void read<Control[]>(`/control-instances?${params}`, controller.signal).then((data) => {
          if (!controller.signal.aborted) setControls(data);
        }).catch((cause) => { if (!controller.signal.aborted) { setControls([]); setError(failure(cause)); } })
          .finally(() => { if (!controller.signal.aborted) setCatalogBusy(false); });
      } else {
        void read<ControlledDocument[]>(`/documents?${params}`, controller.signal).then((data) => {
          if (!controller.signal.aborted) setDocuments(data);
        }).catch((cause) => { if (!controller.signal.aborted) { setDocuments([]); setError(failure(cause)); } })
          .finally(() => { if (!controller.signal.aborted) setCatalogBusy(false); });
      }
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [risk.unit_id, canManage, canReadControls, canReadDocuments, addKind, controlQuery, documentQuery]);

  useEffect(() => {
    const controller = new AbortController();
    if (!documentChoice.id || !canReadDocuments || addKind !== "document") return () => controller.abort();
    const timer = window.setTimeout(() => {
      setRevisionBusy(true); setRevisions([]);
      void read<Revision[]>(`/documents/${documentChoice.id}/revisions`, controller.signal).then((data) => {
        if (!controller.signal.aborted) setRevisions(data.filter((item) => item.status === "active" && item.file_state === "clean"));
      }).catch((cause) => { if (!controller.signal.aborted) { setRevisions([]); setError(failure(cause)); } })
        .finally(() => { if (!controller.signal.aborted) setRevisionBusy(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [documentChoice.id, canReadDocuments, addKind]);

  async function mutate(kind: LinkKind, body: object, link?: RiskLink) {
    if (disabled || mutationBusy.current || !canManage) return;
    mutationBusy.current = true;
    const revision = epoch.current;
    const attempt = ++mutation.current;
    setBusy(true); onBusyChange?.(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/risks/${risk.id}/${route(kind)}${link ? `/${link.id}/remove` : ""}`, {
        method: "POST", credentials: "include", headers: {
          "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "",
        }, body: JSON.stringify(body),
      });
      if (revision !== epoch.current || attempt !== mutation.current) return;
      if (!response.ok) throw new Error(String(response.status));
      const result = await response.json() as RiskLink;
      if (revision !== epoch.current || attempt !== mutation.current) return;
      setRemoval(null); setAddKind(null); setNotice(link ? "Link removed; its history is preserved." : "Related record linked and recorded in the history.");
      onVersionChange(result.risk_row_version);
    } catch (cause) {
      if (revision !== epoch.current || attempt !== mutation.current) return;
      setError(failure(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) {
        if (kind === "control") { setControlLinks([]); setControls([]); setControlError(failure(cause)); }
        else { setDocumentLinks([]); setDocuments([]); setRevisions([]); setDocumentError(failure(cause)); }
        setAddKind(null);
      }
    } finally {
      mutationBusy.current = false;
      if (attempt === mutation.current) setBusy(false);
      onBusyChange?.(false);
    }
  }

  function linkItem(kind: LinkKind, item: RiskLink) {
    const removing = removal?.kind === kind && removal.id === item.id;
    return <li key={item.id} className={item.status === "removed" ? "risk-link-removed" : undefined}>
      <div className="risk-link-heading"><strong>{item.snapshot_code}{item.snapshot_revision ? ` · ${item.snapshot_revision}` : ""}</strong><span className={`qms-grant-status ${item.status === "active" ? "assigned" : "revoked"}`}>{item.status === "active" ? "Linked" : "Removed"}</span></div>
      <p>{item.snapshot_name}</p>
      <small>Linked {dateLabel(item.created_at)} · {kind === "control" ? `Implementation version ${item.linked_target_version}` : "Released revision"} · Current status: {label(item.target_state)}</small>
      {item.status === "removed" && <p className="risk-link-reason">Removed {item.removed_at ? dateLabel(item.removed_at) : ""}: {item.removal_reason}</p>}
      {canManage && item.status === "active" && !removing && <button className="secondary-action compact-action" disabled={busy || disabled || loading} type="button" onClick={() => setRemoval({ kind, id: item.id, reason: "" })}>Remove link</button>}
      {removing && <form className="risk-link-removal" onSubmit={(event) => { event.preventDefault(); if (!removal?.reason.trim()) return; void mutate(kind, { expected_version: risk.row_version, expected_link_version: item.row_version, reason: removal.reason }, item); }}><label>Reason for removing this link<textarea rows={2} required maxLength={500} value={removal.reason} disabled={busy || disabled} onChange={(event) => setRemoval({ kind, id: item.id, reason: event.target.value })} /></label><div><button className="secondary-action compact-action" disabled={busy || disabled || !removal.reason.trim()} type="submit">Confirm removal</button><button className="secondary-action compact-action" disabled={busy || disabled} type="button" onClick={() => setRemoval(null)}>Keep link</button></div></form>}
    </li>;
  }

  function linkList(kind: LinkKind, items: RiskLink[], allowed: boolean, loadError: string) {
    const active = items.filter((item) => item.status === "active");
    const removed = items.filter((item) => item.status === "removed");
    return <section className="risk-link-group" aria-label={kind === "control" ? "Related control implementations" : "Related document revisions"}>
      <div className="risk-link-group-heading"><h5>{kind === "control" ? "Control implementations" : "Controlled document revisions"}</h5>{canManage && allowed && <button className="secondary-action compact-action" type="button" disabled={busy || disabled || loading || !!loadError} onClick={() => { setAddKind(addKind === kind ? null : kind); setError(""); setRemoval(null); }}><Plus aria-hidden="true" size={14} /> Add link</button>}</div>
      {!allowed ? <p className="qms-history-caption">{kind === "control" ? "Control implementation" : "Document"} read responsibility is required to view these related records.</p> : loadError ? <p className="denied-state" role="alert">{loadError}</p> : loading ? <p role="status">Loading related records…</p> : <>
        <ul className="risk-link-list">{active.map((item) => linkItem(kind, item))}</ul>
        {!active.length && <p className="qms-history-caption">No active links on this page.</p>}
        {!!removed.length && <details className="risk-link-history"><summary>Removed links on this page ({removed.length})</summary><ul className="risk-link-list">{removed.map((item) => linkItem(kind, item))}</ul></details>}
        <nav className="risk-pagination" aria-label={`${kind === "control" ? "Control" : "Document"} link pages`}><button type="button" disabled={busy || disabled || linkPages[kind] === 0} onClick={() => setLinkPages((current) => ({ ...current, [kind]: Math.max(0, current[kind] - pageSize) }))}>Previous links</button><span>Page {Math.floor(linkPages[kind] / pageSize) + 1}</span><button type="button" disabled={busy || disabled || items.length < pageSize || linkPages[kind] >= 1_000_000} onClick={() => setLinkPages((current) => ({ ...current, [kind]: current[kind] + pageSize }))}>Next links</button></nav>
      </>}
      {addKind === kind && canManage && allowed && !loadError && <form className="risk-link-editor" onSubmit={(event) => { event.preventDefault(); void mutate(kind, kind === "control" ? { expected_version: risk.row_version, control_instance_id: controlChoice.id } : { expected_version: risk.row_version, document_id: documentChoice.id, document_revision_id: revisionId }); }}><fieldset disabled={busy || disabled || catalogBusy || revisionBusy}>
        <label>Find by code or name<input maxLength={160} value={kind === "control" ? controlQuery.search : documentQuery.search} onChange={(event) => { if (kind === "control") setControlQuery({ search: event.target.value, offset: 0 }); else setDocumentQuery({ search: event.target.value, offset: 0 }); }} /></label>
        {kind === "control" ? <label>Active implementation<select required value={controlChoice.id} onChange={(event) => { const chosen = controls.find((item) => item.id === event.target.value); setControlChoice({ id: event.target.value, name: chosen ? `${chosen.code} · ${chosen.name}` : "Selected implementation" }); }}><option value="">Select an implementation</option>{controlChoice.id && !controls.some((item) => item.id === controlChoice.id && item.status === "active") && <option value={controlChoice.id}>{controlChoice.name}</option>}{controls.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label> : <>
          <label>Active controlled document<select required value={documentChoice.id} onChange={(event) => { const chosen = documents.find((item) => item.id === event.target.value); setDocumentChoice({ id: event.target.value, name: chosen ? `${chosen.code} · ${chosen.title}` : "Selected document" }); setRevisionId(""); setRevisions([]); }}><option value="">Select a document</option>{documentChoice.id && !documents.some((item) => item.id === documentChoice.id && item.status === "active") && <option value={documentChoice.id}>{documentChoice.name}</option>}{documents.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.code} · {item.title}</option>)}</select></label>
          <label>Released revision<select required value={revisionId} onChange={(event) => setRevisionId(event.target.value)}><option value="">Select a released revision</option>{revisions.map((item) => <option key={item.id} value={item.id}>{item.revision}</option>)}</select></label>
          {documentChoice.id && !revisionBusy && !revisions.length && <p className="qms-history-caption">No released, clean revision is currently available for this document.</p>}
        </>}
        <nav className="risk-pagination" aria-label={`${kind === "control" ? "Implementation" : "Document"} selection pages`}><button type="button" disabled={(kind === "control" ? controlQuery.offset : documentQuery.offset) === 0} onClick={() => { if (kind === "control") setControlQuery((current) => ({ ...current, offset: Math.max(0, current.offset - pageSize) })); else setDocumentQuery((current) => ({ ...current, offset: Math.max(0, current.offset - pageSize) })); }}>Previous results</button><span>Page {Math.floor((kind === "control" ? controlQuery.offset : documentQuery.offset) / pageSize) + 1}</span><button type="button" disabled={(kind === "control" ? controls : documents).length < pageSize || (kind === "control" ? controlQuery.offset : documentQuery.offset) >= 1_000_000} onClick={() => { if (kind === "control") setControlQuery((current) => ({ ...current, offset: current.offset + pageSize })); else setDocumentQuery((current) => ({ ...current, offset: current.offset + pageSize })); }}>More results</button></nav>
        <div className="risk-link-editor-actions"><button className="primary-action compact-action" type="submit" disabled={kind === "control" ? !controlChoice.id : !documentChoice.id || !revisionId}>Link record</button><button className="secondary-action compact-action" type="button" onClick={() => setAddKind(null)}>Cancel</button></div>
      </fieldset></form>}
    </section>;
  }

  return <section className="risk-links" aria-labelledby={`risk-links-${risk.id}`} aria-busy={busy || loading}>
    <div className="risk-link-group-heading"><h4 id={`risk-links-${risk.id}`}><Link2 size={17} aria-hidden="true" /> Related controls & evidence</h4><button className="secondary-action compact-action" type="button" disabled={busy || disabled} onClick={onRefresh}><RefreshCw size={14} aria-hidden="true" /> Refresh links</button></div>
    <p className="qms-history-caption">Link measures and controlled information from this organizational unit. Each link preserves the reference selected at that time.</p>
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {linkList("control", controlLinks, canReadControls, controlError)}
    {linkList("document", documentLinks, canReadDocuments, documentError)}
    {risk.state === "closed" && <p className="qms-history-caption">Related records are read-only because this risk is closed.</p>}
  </section>;
}
