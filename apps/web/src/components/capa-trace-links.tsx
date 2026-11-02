"use client";

import { Link2, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type CAPAScope = { id: string; unit_id: string; row_version: number; state: string };
type TraceLink = {
  id: string; status: "active" | "removed"; row_version: number;
  control_instance_id: string; evidence_id?: string; snapshot_code: string;
  snapshot_name: string; linked_target_version: number; target_state: string;
  created_at: string; removed_at: string | null; removal_reason: string;
};
type Instance = {
  id: string; code: string; name: string; implementation_status: string;
  status: string; row_version: number;
};
type Evidence = { id: string; name: string; status: string; row_version: number };
type Kind = "control" | "evidence";

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
  if (code === "404") return "The CAPA, implementation or evidence is no longer available with your access.";
  if (code === "409") return "The CAPA or reference changed. Refresh and review the latest version.";
  if (code === "422") return "Select an active implementation or accepted evidence, and provide a removal reason.";
  return "Direct CAPA traceability could not be reached. Try refreshing.";
}

export function CAPATraceLinks({ capa, canRead, canManage, disabled, onChanged, onAccessChanged }: {
  capa: CAPAScope; canRead: boolean; canManage: boolean; disabled: boolean;
  onChanged: () => void; onAccessChanged: () => void;
}) {
  const [controls, setControls] = useState<TraceLink[]>([]);
  const [evidenceLinks, setEvidenceLinks] = useState<TraceLink[]>([]);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState<Kind | null>(null);
  const [search, setSearch] = useState("");
  const [instances, setInstances] = useState<Instance[]>([]);
  const [instanceId, setInstanceId] = useState("");
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [evidenceId, setEvidenceId] = useState("");
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [removing, setRemoving] = useState<{ kind: Kind; link: TraceLink } | null>(null);
  const [reason, setReason] = useState("");
  const scope = useRef(0);
  const canWrite = canRead && canManage && ["draft", "analysis", "action_planned", "implementation"].includes(capa.state);

  useEffect(() => { const epoch = scope; ++epoch.current; return () => { ++epoch.current; }; }, [capa.id, capa.unit_id]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      if (!canRead) { setControls([]); setEvidenceLinks([]); setLoading(false); return; }
      setLoading(true); setLoadError("");
      void Promise.all([
        read<TraceLink[]>(`/capas/${capa.id}/control-links?limit=${pageSize}&offset=${offset}`, controller.signal),
        read<TraceLink[]>(`/capas/${capa.id}/evidence-links?limit=${pageSize}&offset=${offset}`, controller.signal),
      ]).then(([controlRows, evidenceRows]) => {
        if (!controller.signal.aborted) { setControls(controlRows); setEvidenceLinks(evidenceRows); }
      }).catch((cause) => {
        if (!controller.signal.aborted) {
          setControls([]); setEvidenceLinks([]); setLoadError(failure(cause));
          if (cause instanceof Error && ["401", "403"].includes(cause.message)) onAccessChanged();
        }
      }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [capa.id, capa.row_version, canRead, offset, reload, onAccessChanged]);

  useEffect(() => {
    const controller = new AbortController();
    if (!adding || !canWrite) return () => controller.abort();
    const params = new URLSearchParams({ unit_id: capa.unit_id, search: search.trim(), limit: String(pageSize), offset: "0" });
    const timer = window.setTimeout(() => {
      setCatalogLoading(true);
      void read<Instance[]>(`/control-instances?${params}`, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setInstances(data.filter((item) => item.status === "active")); })
        .catch((cause) => { if (!controller.signal.aborted) { setInstances([]); setError(failure(cause)); } })
        .finally(() => { if (!controller.signal.aborted) setCatalogLoading(false); });
    }, 150);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [adding, canWrite, capa.unit_id, search]);

  useEffect(() => {
    const controller = new AbortController();
    if (adding !== "evidence" || !instanceId || !canWrite) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setCatalogLoading(true);
      void read<Evidence[]>(`/control-instance-evidence?instance_id=${encodeURIComponent(instanceId)}&limit=200`, controller.signal)
        .then((data) => { if (!controller.signal.aborted) setEvidence(data.filter((item) => item.status === "accepted")); })
        .catch((cause) => { if (!controller.signal.aborted) { setEvidence([]); setError(failure(cause)); } })
        .finally(() => { if (!controller.signal.aborted) setCatalogLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [adding, instanceId, canWrite]);

  function resetEditor() {
    setAdding(null); setRemoving(null); setReason(""); setSearch("");
    setInstanceId(""); setEvidenceId(""); setEvidence([]);
  }

  async function mutate(kind: Kind, body: object, link?: TraceLink) {
    if (busy || disabled || !canWrite) return;
    const epoch = scope.current;
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${capa.id}/${kind}-links${link ? `/${link.id}/remove` : ""}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(String(response.status));
      if (epoch !== scope.current) return;
      resetEditor();
      setNotice(link ? "Reference removed; its versioned history remains available." : kind === "control" ? "Control implementation linked directly to this CAPA." : "Accepted evidence linked directly to this CAPA.");
      setReload((value) => value + 1); onChanged();
    } catch (cause) {
      if (epoch !== scope.current) return;
      setError(failure(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) onAccessChanged();
    } finally { if (epoch === scope.current) setBusy(false); }
  }

  function linkList(kind: Kind, rows: TraceLink[]) {
    return rows.length ? <ul className="ncr-record-list">{rows.map((item) => <li key={item.id}>
      <div className="ncr-list-heading"><strong>{item.snapshot_code}</strong><span className="process-status">{item.status}</span></div>
      <p>{item.snapshot_name}</p>
      <small>Version {item.linked_target_version} · current status: {item.target_state.replaceAll("_", " ")} · linked {new Date(item.created_at).toLocaleDateString()}</small>
      {item.status === "removed" && <small>Removed {item.removed_at ? new Date(item.removed_at).toLocaleDateString() : ""} · {item.removal_reason}</small>}
      {canWrite && item.status === "active" && <button className="secondary-action compact-action" type="button" disabled={busy || disabled} onClick={() => { setRemoving({ kind, link: item }); setReason(""); }}>Remove reference</button>}
      {removing?.link.id === item.id && <form onSubmit={(event) => { event.preventDefault(); if (reason.trim()) void mutate(kind, { expected_version: capa.row_version, expected_link_version: item.row_version, reason: reason.trim() }, item); }}><label>Reason for removal<textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} required /></label><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit" disabled={busy || !reason.trim()}>Confirm removal</button><button className="secondary-action compact-action" type="button" onClick={() => setRemoving(null)}>Cancel</button></div></form>}
    </li>)}</ul> : <p className="ncr-empty">No {kind === "control" ? "control implementations" : "accepted evidence"} linked directly to this CAPA.</p>;
  }

  const rowsOnPage = Math.max(controls.length, evidenceLinks.length);
  return <section className="ncr-editor" aria-label="Direct CAPA controls and evidence" aria-busy={loading || busy}>
    <div className="ncr-detail-heading"><div><p className="eyebrow">Direct traceability</p><h4><Link2 size={17} aria-hidden="true" /> CAPA controls and evidence</h4></div><div className="ncr-form-actions"><button className="secondary-action compact-action" type="button" disabled={disabled || busy} onClick={() => setReload((value) => value + 1)} aria-label="Refresh direct CAPA traceability"><RefreshCw size={15} aria-hidden="true" /></button>{canWrite && <><button className="secondary-action compact-action" type="button" disabled={disabled || busy} onClick={() => { resetEditor(); setAdding("control"); }}><Plus size={15} aria-hidden="true" /> Link control</button><button className="secondary-action compact-action" type="button" disabled={disabled || busy} onClick={() => { resetEditor(); setAdding("evidence"); }}><Plus size={15} aria-hidden="true" /> Link evidence</button></>}</div></div>
    <p className="qms-history-caption"><ShieldCheck size={15} aria-hidden="true" /> Direct references preserve the target name, version and audit history. Evidence must be independently accepted. Links lock when effectiveness review begins.</p>
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {adding && canWrite && <form className="ncr-editor" onSubmit={(event) => { event.preventDefault(); if (adding === "control" && instanceId) void mutate("control", { expected_version: capa.row_version, control_instance_id: instanceId }); if (adding === "evidence" && evidenceId) void mutate("evidence", { expected_version: capa.row_version, evidence_id: evidenceId }); }}><fieldset disabled={busy || disabled}><legend>{adding === "control" ? "Link a control implementation" : "Link independently accepted evidence"}</legend><label>Search implementations<input value={search} maxLength={160} onChange={(event) => setSearch(event.target.value)} /></label><label>Control implementation<select value={instanceId} onChange={(event) => { setInstanceId(event.target.value); setEvidenceId(""); setEvidence([]); }} disabled={catalogLoading}><option value="">Select an active implementation</option>{instances.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name} · {item.implementation_status.replaceAll("_", " ")}</option>)}</select></label>{adding === "evidence" && <><label>Accepted evidence<select value={evidenceId} onChange={(event) => setEvidenceId(event.target.value)} disabled={!instanceId || catalogLoading}><option value="">Select accepted evidence</option>{evidence.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{instanceId && !catalogLoading && !evidence.length && <p className="qms-history-caption">This implementation has no independently accepted evidence.</p>}</>}<div className="ncr-form-actions"><button className="primary-action compact-action" type="submit" disabled={!instanceId || (adding === "evidence" && !evidenceId)}>{adding === "control" ? "Link implementation" : "Link accepted evidence"}</button><button className="secondary-action compact-action" type="button" onClick={resetEditor}>Cancel</button></div></fieldset></form>}
    {loading ? <RecordWorkspaceSkeleton label="Loading direct CAPA traceability" /> : loadError ? <div className="ncr-empty" role="alert"><strong>Direct traceability could not load</strong><p>{loadError}</p><button className="secondary-action compact-action" type="button" onClick={() => setReload((value) => value + 1)}>Retry</button></div> : <div className="risk-link-groups"><div className="risk-link-group"><h5>Control implementations</h5>{linkList("control", controls)}</div><div className="risk-link-group"><h5>Accepted evidence</h5>{linkList("evidence", evidenceLinks)}</div></div>}
    <nav className="ncr-pagination" aria-label="Direct CAPA traceability pages"><button type="button" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</button><span>Page {Math.floor(offset / pageSize) + 1}</span><button type="button" disabled={loading || !!loadError || rowsOnPage < pageSize} onClick={() => setOffset(offset + pageSize)}>Next</button></nav>
  </section>;
}
