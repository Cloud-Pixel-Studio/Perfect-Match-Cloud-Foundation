"use client";

import { ArrowUpRight, Building2, CalendarCheck, HardDrive, KeyRound, ScrollText, ShieldCheck, UserRound, UsersRound } from "lucide-react";
import type { WorkspaceId } from "../lib/workspace-navigation";
import { ThemeToggle } from "./theme-toggle";

const companyAreas = [
  { id: "organization", icon: Building2, name: "Organization structure", description: "Manage sites, departments and unit assignments." },
  { id: "employees", icon: UsersRound, name: "Employee directory", description: "Create, update and archive employee profiles." },
  { id: "company-storage", icon: HardDrive, name: "Storage usage", description: "See how much space your documents and employee photos occupy." },
  { id: "permissions", icon: KeyRound, name: "Permissions", description: "Assign QMS responsibilities by organizational unit." },
  { id: "implementation-guide", icon: CalendarCheck, name: "QMS implementation", description: "Plan a rollout and review your company’s implementation records." },
  { id: "audit", icon: ScrollText, name: "Audit trail", description: "Review recorded changes and the people who made them." },
] as const;

export function CompanyControl({ name, role, onNavigate }: {
  name: string; role: string; onNavigate: (id: WorkspaceId) => void;
}) {
  return <section className="cc-workspace" aria-labelledby="company-control-heading">
    <header className="cc-workspace-header">
      <span className="cc-icon"><Building2 aria-hidden="true" size={23} /></span>
      <div>
        <p className="cc-overline">{name}</p>
        <h2 id="company-control-heading">Company control</h2>
        <p>Manage your company’s structure, access and quality implementation.</p>
      </div>
      <span className="cc-chip"><ShieldCheck aria-hidden="true" size={15} /> {role === "owner" ? "Company owner" : "Company administrator"}</span>
    </header>
    <div className="cc-link-grid">
      {companyAreas.map(({ id, icon: Icon, name: label, description }) =>
        <button key={id} type="button" className="cc-workspace-link" onClick={() => onNavigate(id)}>
          <Icon className="cc-link-icon" aria-hidden="true" size={22} />
          <strong>{label}</strong>
          <span>{description}</span>
          <ArrowUpRight className="cc-link-arrow" aria-hidden="true" size={18} />
        </button>
      )}
    </div>
  </section>;
}

export function PersonalProfile({ name, email, company, role }: {
  name: string; email: string | null; company: string; role: string;
}) {
  return <section className="cc-workspace" aria-labelledby="my-profile-heading">
    <header className="cc-workspace-header">
      <span className="cc-icon"><UserRound aria-hidden="true" size={23} /></span>
      <div>
        <p className="cc-overline">Your account</p>
        <h2 id="my-profile-heading">My profile</h2>
        <p>Review your sign-in identity and personal appearance preference.</p>
      </div>
    </header>
    <div className="cc-profile-grid">
      <section className="cc-card" aria-labelledby="cc-identity-heading">
        <h3 id="cc-identity-heading">Account details</h3>
        <dl className="cc-facts">
          <div><dt>Name</dt><dd>{name}</dd></div>
          <div><dt>Email</dt><dd>{email || "Unavailable"}</dd></div>
          <div><dt>Current company</dt><dd>{company}</dd></div>
          <div><dt>Company role</dt><dd className="cc-capitalized">{role}</dd></div>
        </dl>
      </section>
      <section className="cc-card" aria-labelledby="cc-appearance-heading">
        <h3 id="cc-appearance-heading">Appearance</h3>
        <p>Your theme preference applies in this browser.</p>
        <ThemeToggle />
      </section>
    </div>
  </section>;
}
