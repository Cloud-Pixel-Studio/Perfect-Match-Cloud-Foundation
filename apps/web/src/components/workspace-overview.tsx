"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  Building2,
  ChartNoAxesCombined,
  BarChart3,
  ClipboardCheck,
  FileText,
  FolderKanban,
  KeyRound,
  ListChecks,
  ScrollText,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import { type WorkspaceId, type WorkspaceItem, type WorkspaceTarget } from "../lib/workspace-navigation";
import { ActionCenterWorkspace } from "./action-center-workspace";
import { canPreviewQualityTrends, visibleDashboardMetrics } from "../lib/dashboard-metrics";

const overviewIcons: Partial<Record<WorkspaceId, LucideIcon>> = {
  processes: FolderKanban,
  documents: FileText,
  controls: ListChecks,
  risks: ChartNoAxesCombined,
  nonconformities: AlertTriangle,
  capa: ClipboardCheck,
  organization: Building2,
  permissions: KeyRound,
  workflows: Workflow,
  audit: ScrollText,
};

export function WorkspaceOverview({ tenantName, role, sections, onNavigate }: { tenantName: string; role: string; sections: { label: string; items: WorkspaceItem[] }[]; onNavigate: (id: WorkspaceId, target?: WorkspaceTarget | null) => void }) {
  const visibleMetrics = visibleDashboardMetrics(sections);
  return <section className="qms-overview" aria-labelledby="overview-heading">
    <div className="qms-overview-hero">
      <div>
        <p className="eyebrow"><span /> Your quality system</p>
        <h2 id="overview-heading">Work with clarity.<br /><em>Improve with evidence.</em></h2>
        <p>Open the area you need. Every record stays within your organization and its assigned responsibilities.</p>
      </div>
      <div className="qms-overview-context"><span className="qms-overview-context-icon"><ShieldCheck aria-hidden="true" size={22} /></span><span><small>Private tenant workspace</small><strong>{tenantName}</strong><span>Current role: {role}</span></span></div>
    </div>
    {visibleMetrics.length > 0 && <section className="qms-insights" aria-labelledby="qms-insights-heading">
      <div className="qms-insights-heading">
        <div><p className="eyebrow">Quality intelligence</p><h3 id="qms-insights-heading">Performance overview</h3></div>
        <span className="qms-insights-status">Analytics in preparation</span>
      </div>
      <p className="qms-insights-description">Indicators will appear when verified, organization-scoped reporting is available. No sample values are shown in your live workspace.</p>
      <div className="qms-insights-grid">
        {visibleMetrics.map((metric) => <article className="qms-insights-card" key={metric.module}>
          <span className="qms-insights-label">{metric.label}</span>
          <strong className="qms-insights-value" aria-label="Metric not yet available">—</strong>
          <small>{metric.detail}</small>
          <button type="button" onClick={() => onNavigate(metric.module)}>Open {metric.module === "capa" ? "CAPA" : metric.module} <ArrowUpRight aria-hidden="true" size={15} /></button>
        </article>)}
      </div>
      {canPreviewQualityTrends(visibleMetrics) && <div className="qms-insights-chart-placeholder">
        <BarChart3 aria-hidden="true" size={21} />
        <span><strong>Trends and charts are coming next</strong><small>Historical series require validated, permission-scoped source data.</small></span>
      </div>}
    </section>}
    <ActionCenterWorkspace compact role={role} onNavigate={onNavigate} />
    <div className="qms-overview-sections">
      {sections.slice(1).map((section) => {
        const visibleItems = section.items;
        return <section key={section.label} aria-label={section.label}>
        <div className="qms-overview-section-heading"><p className="eyebrow">{section.label}</p><span>{visibleItems.length} areas</span></div>
        <div className="qms-overview-grid">{visibleItems.map((item, index) => {
          const Icon = overviewIcons[item.id] ?? ShieldCheck;
          return <a className="qms-overview-card" href={`#${item.hash}`} key={item.id} onClick={(event) => { event.preventDefault(); onNavigate(item.id); }}>
          <span className="qms-overview-card-icon"><Icon aria-hidden="true" size={20} /></span>
          <span><strong>{item.label}</strong><small>{item.description}</small></span>
          <span className="qms-overview-card-arrow"><span className="sr-only">Open {item.label}</span><ArrowUpRight aria-hidden="true" size={17} /></span>
          <span className="qms-overview-card-number">{String(index + 1).padStart(2, "0")}</span>
        </a>;
        })}</div>
      </section>; })}
    </div>
  </section>;
}
