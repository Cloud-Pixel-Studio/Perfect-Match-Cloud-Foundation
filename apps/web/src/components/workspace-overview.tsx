"use client";

import {
  AlertTriangle,
  ArrowUpRight,
  Building2,
  ChartNoAxesCombined,
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
  return <section className="qms-overview" aria-labelledby="overview-heading">
    <div className="qms-overview-hero">
      <div>
        <p className="eyebrow"><span /> Your quality system</p>
        <h2 id="overview-heading">Work with clarity.<br /><em>Improve with evidence.</em></h2>
        <p>Open the area you need. Every record stays within your organization and its assigned responsibilities.</p>
      </div>
      <div className="qms-overview-context"><span className="qms-overview-context-icon"><ShieldCheck aria-hidden="true" size={22} /></span><span><small>Private tenant workspace</small><strong>{tenantName}</strong><span>Current role: {role}</span></span></div>
    </div>
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
