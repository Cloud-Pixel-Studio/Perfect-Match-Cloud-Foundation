"use client";

import { Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { auditPlanFilename, collectAuditPlan, PlanExportError, renderAuditPlan, type PlanSelection } from "../lib/audit-plan-export";

export function AuditPlanDownload({ audit, unitLabel, disabled, onBusyChange, onAccessChanged }: {
  audit: PlanSelection; unitLabel: string; disabled: boolean;
  onBusyChange: (value: boolean) => void; onAccessChanged: (status: number) => void;
}) {
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  const active = useRef<AbortController | null>(null);
  const callbacks = useRef({ onBusyChange, onAccessChanged });
  useEffect(() => { callbacks.current = { onBusyChange, onAccessChanged }; }, [onBusyChange, onAccessChanged]);
  useEffect(() => () => {
    active.current?.abort();
    if (active.current) callbacks.current.onBusyChange(false);
    active.current = null;
  }, [audit.id, audit.unit_id, audit.row_version]);
  async function download() {
    if (active.current || disabled) return;
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setError(""); setNotice(""); callbacks.current.onBusyChange(true);
    try {
      const plan = await collectAuditPlan(audit, unitLabel, controller.signal);
      if (active.current !== controller || controller.signal.aborted) return;
      const url = URL.createObjectURL(new Blob([renderAuditPlan(plan)], { type: "text/html;charset=utf-8" }));
      const link = document.createElement("a"); link.href = url; link.download = auditPlanFilename(plan);
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("Plan downloaded. Open the HTML file to print or save as PDF.");
    } catch (cause) {
      if (active.current === controller && !controller.signal.aborted) {
        controller.abort();
        setError(cause instanceof PlanExportError ? cause.message : "The plan could not be downloaded. Refresh and try again.");
        if (cause instanceof PlanExportError && cause.status && [401, 403, 404].includes(cause.status)) callbacks.current.onAccessChanged(cause.status);
      }
    } finally {
      if (active.current === controller) {
        active.current = null; setBusy(false); callbacks.current.onBusyChange(false);
      }
    }
  }
  return <section className="ncr-read-section" aria-label="Audit plan download" aria-busy={busy}>
    <div className="ncr-form-actions"><button type="button" className="secondary-action compact-action" disabled={disabled || busy} onClick={() => void download()}><Download size={16} aria-hidden="true" />{busy ? "Preparing plan…" : "Download audit plan"}</button>
      {busy && <button type="button" className="secondary-action compact-action" onClick={() => { active.current?.abort(); setNotice("Plan download cancelled."); }}>Cancel download</button>}</div>
    <p className="qms-history-caption">HTML · Print-ready planning copy with scope, criteria, team and agenda. Includes withdrawn items and their reasons.</p>
    {busy && <p role="status">Collecting the current plan…</p>}{error && <p role="alert" className="error-notice">{error}</p>}{notice && <p role="status" className="success-notice">{notice}</p>}
  </section>;
}
