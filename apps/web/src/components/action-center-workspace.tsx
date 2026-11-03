"use client";

import { AlertCircle, ArrowRight, CalendarClock, CheckCircle2, ClipboardList, RefreshCw, UserRound } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { WorkspaceId } from "../lib/workspace-navigation";

type ActionItem = {
  id: string;
  source: "workflow" | "capa" | "control_activity" | "evidence_review";
  source_id: string;
  unit_id: string | null;
  title: string;
  context: string;
  state: string;
  urgency: "overdue" | "due_soon" | "normal" | "waiting_review";
  due_date: string | null;
  overdue: boolean;
  assigned_to_user_id: string | null;
  assignee_name: string | null;
  target_workspace: "workflows" | "capa" | "controls";
  updated_at: string;
};

type ActionCenterResponse = {
  scope: "mine" | "team";
  generated_at: string;
  summary: { total: number; overdue: number; due_soon: number; unassigned: number; by_source: Record<string, number> };
  items: ActionItem[];
};

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

export function ActionCenterWorkspace({ role, compact = false, onNavigate }: { role: string; compact?: boolean; onNavigate: (id: WorkspaceId) => void }) {
  const [scope, setScope] = useState<"mine" | "team">("mine");
  const [data, setData] = useState<ActionCenterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestRevision = useRef(0);
  const canViewTeam = ["owner", "admin", "auditor"].includes(role);

  const load = useCallback(async (requestedScope: "mine" | "team") => {
    const revision = ++requestRevision.current;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/identity/action-center?scope=${requestedScope}&limit=${compact ? 5 : 100}`, { credentials: "include" });
      if (!response.ok) throw new Error(response.status === 403 ? "Team oversight is not assigned to this role." : "The action center is temporarily unavailable.");
      const result = (await response.json()) as ActionCenterResponse;
      if (revision === requestRevision.current) setData(result);
    } catch (reason) {
      if (revision === requestRevision.current) setError(reason instanceof Error ? reason.message : "The action center is temporarily unavailable.");
    } finally {
      if (revision === requestRevision.current) setLoading(false);
    }
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
          <button aria-pressed={scope === "mine"} onClick={() => setScope("mine")} type="button">My actions</button>
          <button aria-pressed={scope === "team"} onClick={() => setScope("team")} type="button">Team view</button>
        </div>}
        <button className="icon-button" disabled={loading} onClick={() => void load(scope)} title="Refresh action center" type="button"><RefreshCw aria-hidden="true" size={17} /><span className="sr-only">Refresh action center</span></button>
      </div>
    </div>

    {error && <p className="denied-state" role="alert">{error}</p>}
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
          <button aria-label={`Open ${item.title}`} onClick={() => onNavigate(item.target_workspace)} type="button">Open <ArrowRight aria-hidden="true" size={16} /></button>
        </li>)}
      </ol>}
      {compact && <button className="action-center-link" onClick={() => onNavigate("actions")} type="button">Open action center <ArrowRight aria-hidden="true" size={16} /></button>}
      <p className="action-generated">Updated {new Date(data.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}. Counts reflect records you are authorized to view.</p>
    </>}
  </section>;
}
