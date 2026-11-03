"use client";

import { ArrowUpRight, ShieldCheck } from "lucide-react";

import { workspaceSections, type WorkspaceId } from "../lib/workspace-navigation";
import { ActionCenterWorkspace } from "./action-center-workspace";

export function WorkspaceOverview({ tenantName, role, canAudit, onNavigate }: { tenantName: string; role: string; canAudit: boolean; onNavigate: (id: WorkspaceId) => void }) {
  return <section className="qms-overview" aria-labelledby="overview-heading">
    <div className="qms-overview-hero">
      <div>
        <p className="eyebrow">Your quality system</p>
        <h2 id="overview-heading">Work with clarity.</h2>
        <p>Open the area you need. Every record stays within your organization and its assigned responsibilities.</p>
      </div>
      <div className="qms-overview-context"><ShieldCheck aria-hidden="true" size={22} /><span><strong>{tenantName}</strong><small>Current role: {role}</small></span></div>
    </div>
    <ActionCenterWorkspace compact role={role} onNavigate={onNavigate} />
    <div className="qms-overview-sections">
      {workspaceSections.slice(1).map((section) => {
        const visibleItems = section.items.filter((item) => item.id !== "audit" || canAudit);
        return <section key={section.label} aria-label={section.label}>
        <div className="qms-overview-section-heading"><p className="eyebrow">{section.label}</p><span>{visibleItems.length} areas</span></div>
        <div className="qms-overview-grid">{visibleItems.map((item, index) => <a className="qms-overview-card" href={`#${item.hash}`} key={item.id} onClick={(event) => { event.preventDefault(); onNavigate(item.id); }}>
          <span className="qms-overview-card-number">{String(index + 1).padStart(2, "0")}</span>
          <span><strong>{item.label}</strong><small>{item.description}</small></span>
          <ArrowUpRight aria-hidden="true" size={18} />
        </a>)}</div>
      </section>; })}
    </div>
  </section>;
}
