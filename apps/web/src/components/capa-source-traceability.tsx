"use client";

import { Link2, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Source = {
  source_type: "ncr" | "risk" | "other";
  source_ncr_id: string | null;
  source_risk_id: string | null;
};
type TraceLink = {
  id: string;
  status: "active" | "removed";
  snapshot_code: string;
  snapshot_name: string;
  target_state: string;
  created_at: string;
};

const api = "/api/identity";

async function read(path: string, signal: AbortSignal): Promise<TraceLink[]> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as TraceLink[];
}

export function CAPASourceTraceability({ source }: { source: Source }) {
  const sourceId = source.source_type === "ncr" ? source.source_ncr_id : source.source_risk_id;
  const [controls, setControls] = useState<TraceLink[]>([]);
  const [evidence, setEvidence] = useState<TraceLink[]>([]);
  const [loading, setLoading] = useState(Boolean(sourceId));
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    if (!sourceId || source.source_type === "other") return () => controller.abort();
    const base = source.source_type === "ncr" ? `/nonconformities/${sourceId}` : `/risks/${sourceId}`;
    const timer = window.setTimeout(() => {
      setLoading(true); setError("");
      const requests = [read(`${base}/control-links?limit=100`, controller.signal)];
      if (source.source_type === "ncr") requests.push(read(`${base}/evidence-links?limit=100`, controller.signal));
      void Promise.all(requests)
        .then(([controlRows, evidenceRows = []]) => {
          if (!controller.signal.aborted) {
            setControls(controlRows.filter((item) => item.status === "active"));
            setEvidence(evidenceRows.filter((item) => item.status === "active"));
          }
        })
        .catch((cause) => {
          if (!controller.signal.aborted) {
            setControls([]); setEvidence([]);
            setError(cause instanceof Error && ["401", "403"].includes(cause.message)
              ? "Source traceability is restricted by your control or evidence responsibilities."
              : "Source traceability could not be loaded.");
          }
        })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [source.source_type, sourceId, reload]);

  if (!sourceId || source.source_type === "other") return null;
  const rows = [
    ...controls.map((item) => ({ ...item, kind: "Control implementation" })),
    ...evidence.map((item) => ({ ...item, kind: "Accepted evidence" })),
  ];

  return <section className="ncr-editor" aria-label="CAPA source traceability" aria-busy={loading}>
    <div className="ncr-detail-heading"><div><p className="eyebrow">Inherited traceability</p><h4><Link2 size={17} aria-hidden="true" /> Source controls and evidence</h4></div><button className="secondary-action compact-action" type="button" disabled={loading} onClick={() => setReload((value) => value + 1)} aria-label="Refresh source traceability"><RefreshCw size={15} aria-hidden="true" /></button></div>
    <p className="qms-history-caption"><ShieldCheck size={15} aria-hidden="true" /> These references come from the registered source and remain governed by the source record&apos;s permissions and history.</p>
    {loading ? <RecordWorkspaceSkeleton label="Loading source traceability" /> : error ? <div className="ncr-empty" role="alert"><strong>Additional traceability unavailable</strong><p>{error}</p></div> : rows.length ? <ul className="ncr-record-list">{rows.map((item) => <li key={`${item.kind}-${item.id}`}><div className="ncr-list-heading"><strong>{item.snapshot_code}</strong><span className="process-status">{item.kind}</span></div><p>{item.snapshot_name}</p><small>Current status: {item.target_state.replaceAll("_", " ")} · linked {new Date(item.created_at).toLocaleDateString()}</small></li>)}</ul> : <p className="ncr-empty">The source has no active control or evidence references.</p>}
  </section>;
}
