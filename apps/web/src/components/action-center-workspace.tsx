"use client";

import { AlertCircle, ArrowRight, CalendarClock, CheckCircle2, ClipboardList, LockKeyhole, LogIn, RefreshCw, UserRound } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { WorkspaceId, WorkspaceTarget } from "../lib/workspace-navigation";
import { fetchActions, type ActionCenterResponse, type ActionFailure, type ActionItem } from "../lib/action-center-data";

const sourceLabels: Record<ActionItem["source"], string> = {
  workflow: "Workflow",
  capa: "CAPA",
  control_activity: "Control activity",
  evidence_review: "Evidence review",
};

const urgencyLabels: Record<ActionItem["urgency"], string> = {
  overdue: "Overdue",
  due_soon: "Due soon",
  normal: "Open",
  waiting_review: "Review needed",
};

function readable(value: string): string {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function ActionCenterWorkspace({ role, compact = false, onNavigate }: { role: string; compact?: boolean; onNavigate: (id: WorkspaceId, target?: WorkspaceTarget | null) => void }) {
  const [scope, setScope] = useState<"mine" | "team">("mine");
  const [data, setData] = useState<ActionCenterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ActionFailure | null>(null);
  const requestRevision = useRef(0);
  const canViewTeam = ["owner", "admin", "auditor"].includes(role);

  const load = useCallback(async (requestedScope: "mine" | "team") => {
    const revision = ++requestRevision.current;
    setLoading(true);
    setError(null);
    setData(null);
    const result = await fetchActions(requestedScope, compact ? 5 : 100);
    if (revision !== requestRevision.current) return;
    if (result.ok) setData(result.data);
    else setError(result.reason);
    setLoading(false);
  }, [compact]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(scope), 0);
    return () => {
      window.clearTimeout(timer);
      requestRevision.current += 1;
    };
  }, [load, scope]);

  const items = compact ? data?.items.slice(0, 5) ?? [] : data?.items ?? [];
  return <section className={`action-center ${compact ? "action-center-compact" : ""}`} aria-labelledby={compact ? "overview-actions-heading" : "action-center-heading"} aria-busy={loading}>
    <div className="action-center-heading">
      <div>
        <p className="eyebrow">Operational focus</p>
        <h2 id={compact ? "overview-actions-heading" : "action-center-heading"}>{compact ? "What needs attention" : "Action center"}</h2>
        <p>{compact ? "Your live priorities across the quality system." : "One prioritized queue derived from workflows, corrective actions, controls and evidence reviews."}</p>
      </div>
      <div className="action-center-tools">
        {!compact && canViewTeam && <div className="action-scope" aria-label="Action center scope">
          <button aria-pressed={scope === "mine"} disabled={loading || error === "expired"} onClick={() => setScope("mine")} type="button">My actions</button>
          <button aria-pressed={scope === "team"} disabled={loading || error === "expired"} onClick={() => setScope("team")} type="button">Team view</button>
        </div>}
        <button className="icon-button" disabled={loading || error === "expired"} onClick={() => void load(scope)} title="Refresh action center" type="button"><RefreshCw aria-hidden="true" size={17} /><span className="sr-only">Refresh action center</span></button>
      </div>
    </div>

    {error === "expired" ? <div className="action-session-recovery" role="alert">
      <LockKeyhole aria-hidden="true" size={23} />
      <div><h3>Your session has expired</h3><p>Sign in again to load your current actions.</p>
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- OIDC login must be a full browser navigation; never prefetch its session-changing GET. */}
        <a className="primary-action" href="/api/identity/auth/login"><LogIn aria-hidden="true" size={17} />Sign in again</a>
      </div>
    </div> : error && <p className="denied-state" role="alert">{error === "denied" ? "You no longer have access to this action view." : "The action center is temporarily unavailable."}</p>}
    {loading && !data ? <div className="action-loading" role="status"><span /><span /><span />Loading priorities…</div> : data && <>
      <div className="action-metrics" aria-label="Action summary">
        <article><ClipboardList aria-hidden="true" size={20} /><span><strong>{data.summary.total}</strong><small>Open actions</small></span></article>
        <article className={data.summary.overdue > 0 ? "metric-danger" : ""}><AlertCircle aria-hidden="true" size={20} /><span><strong>{data.summary.overdue}</strong><small>Overdue</small></span></article>
        <article><CalendarClock aria-hidden="true" size={20} /><span><strong>{data.summary.due_soon}</strong><small>Due in 7 days</small></span></article>
        {!compact && <article><UserRound aria-hidden="true" size={20} /><span><strong>{data.summary.unassigned}</strong><small>Shared or unassigned</small></span></article>}
      </div>
      {items.length === 0 ? <div className="action-empty"><CheckCircle2 aria-hidden="true" size={24} /><div><strong>No actions need your attention.</strong><p>New assigned work and pending reviews will appear here automatically.</p></div></div> : <ol className="action-list">
        {items.map((item) => <li key={item.id} className={`action-item urgency-${item.urgency}`}>
          <div className="action-item-main">
            <div className="action-item-labels"><span>{sourceLabels[item.source]}</span><span className={`urgency-badge urgency-${item.urgency}`}>{urgencyLabels[item.urgency]}</span></div>
            <strong>{item.title}</strong>
            <small>{item.context}</small>
          </div>
          <dl>
            <div><dt>Status</dt><dd>{readable(item.state)}</dd></div>
            <div><dt>Due</dt><dd>{item.due_date ? new Date(`${item.due_date}T12:00:00`).toLocaleDateString() : "No date"}</dd></div>
            {!compact && <div><dt>Owner</dt><dd>{item.assignee_name ?? (item.assigned_to_user_id ? "Assigned member" : "Authorized reviewer")}</dd></div>}
          </dl>
          <button aria-label={`Open ${item.title}`} onClick={() => onNavigate(item.target_workspace, {
            recordId: item.target_record_id,
            subrecordId: item.target_subrecord_id ?? undefined,
            source: item.source,
            unitId: item.unit_id ?? undefined,
            processId: item.target_process_id ?? undefined,
          })} type="button">Open <ArrowRight aria-hidden="true" size={16} /></button>
        </li>)}
      </ol>}
      {compact && <button className="action-center-link" onClick={() => onNavigate("actions")} type="button">Open action center <ArrowRight aria-hidden="true" size={16} /></button>}
      <p className="action-generated">Updated {new Date(data.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}. Counts reflect records you are authorized to view.</p>
    </>}
  </section>;
}
