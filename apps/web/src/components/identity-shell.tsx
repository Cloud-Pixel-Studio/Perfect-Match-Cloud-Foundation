"use client";

import { AlertTriangle, Building2, CalendarRange, ChartNoAxesCombined, ChevronDown, ClipboardCheck, ClipboardList, FileText, FolderKanban, KeyRound, LayoutDashboard, ListChecks, LogIn, LogOut, ScrollText, ShieldCheck, UserRound, Workflow as WorkflowIcon, type LucideIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ThemeToggle } from "./theme-toggle";
import { OrganizationWorkspace } from "./organization-workspace";
import { ProcessWorkspace } from "./process-workspace";
import { QMSAccessWorkspace } from "./qms-access-workspace";
import { WorkflowWorkspace } from "./workflow-workspace";
import { DocumentsWorkspace } from "./documents-workspace";
import { ControlsWorkspace } from "./controls-workspace";
import { RisksWorkspace } from "./risks-workspace";
import { NonconformitiesWorkspace } from "./nonconformities-workspace";
import { CAPAWorkspace } from "./capa-workspace";
import { WorkspaceOverview } from "./workspace-overview";
import { ActionCenterWorkspace } from "./action-center-workspace";
import { AuditWorkspace } from "./audit-workspace";
import { InternalAuditsWorkspace } from "./internal-audits-workspace";
import { type IdentityViewState, unauthenticatedState } from "../lib/identity-state";
import { setWorkspaceTarget, workspaceFromHash, workspaceItems, workspaceSections, workspaceSectionsForContext, workspaceTargetFromSearch, type WorkspaceId, type WorkspaceTarget } from "../lib/workspace-navigation";

type Identity = {
  id: string;
  display_name: string;
  email: string | null;
  current_tenant_id: string | null;
};

type Tenant = { id: string; name: string; slug: string; role: string };
type CapabilitySummary = { capabilities: string[] };
const apiUrl = "/api/identity";
const workspaceIcons: Record<WorkspaceId, LucideIcon> = {
  overview: LayoutDashboard,
  actions: ClipboardList,
  processes: FolderKanban,
  documents: FileText,
  controls: ListChecks,
  "internal-audits": CalendarRange,
  risks: ChartNoAxesCombined,
  nonconformities: AlertTriangle,
  capa: ClipboardCheck,
  organization: Building2,
  permissions: KeyRound,
  workflows: WorkflowIcon,
  audit: ScrollText,
};

function csrfToken(): string {
  const item = document.cookie.split("; ").find((cookie) => cookie.startsWith("pm_csrf="));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : "";
}

export function IdentityShell() {
  const [view, setView] = useState<IdentityViewState>("loading");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [busy, setBusy] = useState(false);
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [activeModule, setActiveModule] = useState<WorkspaceId>("overview");
  const [activeTarget, setActiveTarget] = useState<WorkspaceTarget | null>(null);
  const [unitByTenant, setUnitByTenant] = useState<Record<string, string>>({});
  const contextRevision = useRef(0);
  const contextKey = useRef<string | null>(null);

  const loadIdentity = useCallback(async () => {
    try {
      const me = await fetch(`${apiUrl}/auth/me`, { credentials: "include" });
      if (!me.ok) {
        setView(unauthenticatedState(me.status, document.cookie.includes("pm_csrf=")));
        return;
      }
      const user = (await me.json()) as Identity;
      const [memberships, capabilityResponse] = await Promise.all([
        fetch(`${apiUrl}/auth/tenants`, { credentials: "include" }),
        user.current_tenant_id ? fetch(`${apiUrl}/qms-access/active-capabilities`, { credentials: "include" }) : Promise.resolve(null),
      ]);
      if (!memberships.ok) throw new Error("memberships unavailable");
      if (user.current_tenant_id && !capabilityResponse?.ok) throw new Error("capability summary unavailable");
      const availableTenants = (await memberships.json()) as Tenant[];
      const summary = capabilityResponse?.ok ? (await capabilityResponse.json()) as CapabilitySummary : { capabilities: [] };
      const role = availableTenants.find((tenant) => tenant.id === user.current_tenant_id)?.role ?? "";
      const nextContextKey = `${user.id}:${user.current_tenant_id ?? ""}:${role}`;
      if (contextKey.current !== nextContextKey) {
        contextRevision.current += 1;
        contextKey.current = nextContextKey;
      }
      setCapabilities([...new Set(summary.capabilities)].sort());
      setIdentity(user);
      setTenants(availableTenants);
      setView("authenticated");
    } catch {
      setView("error");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadIdentity(), 0);
    return () => window.clearTimeout(timer);
  }, [loadIdentity]);

  useEffect(() => {
    const sync = () => {
      setActiveModule(workspaceFromHash(window.location.hash));
      setActiveTarget(workspaceTargetFromSearch(window.location.search));
    };
    const frame = window.requestAnimationFrame(sync);
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener("hashchange", sync); window.removeEventListener("popstate", sync); };
  }, []);

  const current = identity ? tenants.find((tenant) => tenant.id === identity.current_tenant_id) : undefined;
  const canAudit = ["owner", "admin", "auditor"].includes(current?.role ?? "");
  const visibleSections = current ? workspaceSectionsForContext(current.role, capabilities) : workspaceSections.slice(0, 1);
  const visibleModuleIds = visibleSections.flatMap((section) => section.items.map((item) => item.id));
  const activeModuleVisible = visibleModuleIds.includes(activeModule);

  useEffect(() => {
    if (view !== "authenticated" || !current || activeModuleVisible) return;
    const overview = workspaceItems.find((item) => item.id === "overview");
    if (!overview) return;
    const timer = window.setTimeout(() => {
      const url = setWorkspaceTarget(new URL(window.location.href), null);
      url.hash = overview.hash;
      window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
      setActiveModule("overview");
      setActiveTarget(null);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [activeModuleVisible, current, view]);

  function navigateWorkspace(id: WorkspaceId, target: WorkspaceTarget | null = null) {
    if (busy) return;
    const item = workspaceItems.find((entry) => entry.id === id);
    if (!item) return;
    const url = setWorkspaceTarget(new URL(window.location.pathname, window.location.origin), target);
    url.hash = item.hash;
    window.history.pushState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setActiveModule(id);
    setActiveTarget(target);
    if (target?.unitId && current) {
      setUnitByTenant((previous) => ({ ...previous, [current.id]: target.unitId as string }));
    }
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  async function selectTenant(tenantId: string) {
    contextRevision.current += 1;
    setBusy(true);
    const response = await fetch(`${apiUrl}/auth/tenant`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
      body: JSON.stringify({ tenant_id: tenantId }),
    });
    if (response.status === 403) setView("denied");
    else if (response.ok) await loadIdentity();
    else setView("error");
    setBusy(false);
  }

  async function logout() {
    contextRevision.current += 1;
    setBusy(true);
    const response = await fetch(`${apiUrl}/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": csrfToken() },
    });
    if (!response.ok) {
      setView(response.status === 403 ? "denied" : "error");
      setBusy(false);
      return;
    }
    setIdentity(null);
    setTenants([]);
    setCapabilities([]);
    setView("anonymous");
    setBusy(false);
  }

  if (view === "loading") {
    return (
      <main className="identity-main" aria-live="polite">
        <p>Checking your secure session...</p>
      </main>
    );
  }

  if (view !== "authenticated" || !identity) {
    const copyByState: Record<IdentityViewState, [string, string]> = {
      anonymous: ["Welcome to Perfect Match", "Use your approved identity provider to continue."],
      authenticated: ["Welcome to Perfect Match", "Select an organization to continue."],
      expired: ["Your session has expired", "Authenticate again to return to your organization."],
      denied: ["Access denied", "Your identity does not have access to the requested organization."],
      error: ["Identity service unavailable", "The local identity boundary could not be reached."],
      loading: ["Checking your secure session", ""],
    };
    const copy = copyByState[view];
    return (
      <main className="identity-main">
        <section className="login-panel" aria-labelledby="login-heading">
          <span className="security-mark"><ShieldCheck aria-hidden="true" size={24} /></span>
          <p className="eyebrow">Secure access</p>
          <h1 id="login-heading">{copy[0]}</h1>
          <p>{copy[1]}</p>
          <a className="primary-action" href={`${apiUrl}/auth/login`}>
            <LogIn aria-hidden="true" size={18} />
            Continue to Perfect Match
          </a>
          <div className="login-footnote">
            <ShieldCheck aria-hidden="true" size={15} />
            Authentication is handled by your identity provider.
          </div>
        </section>
        <ThemeToggle />
      </main>
    );
  }

  const visibleIds = new Set(visibleModuleIds);
  const presentedModule: WorkspaceId = visibleIds.has(activeModule) ? activeModule : "overview";
  const navigationSections = visibleSections;
  const selectedItem = workspaceItems.find((item) => item.id === presentedModule) ?? workspaceItems[0];
  const selectedSection = workspaceSections.find((section) => section.items.some((item) => item.id === presentedModule));
  const preferredUnitId = current ? activeTarget?.unitId ?? unitByTenant[current.id] ?? "" : "";
  const onUnitChange = (unitId: string) => {
    if (current) setUnitByTenant((previous) => ({ ...previous, [current.id]: unitId }));
  };
  return (
    <main className="identity-main authenticated-main qms-app-shell">
      <a className="skip-link" href="#qms-active-workspace">Skip to active workspace</a>
      <aside className="qms-app-sidebar" aria-label="Main navigation">
        <div className="qms-sidebar-intro"><span className="qms-sidebar-kicker">Perfect Match</span><strong>Quality workspace</strong><small>{current?.name ?? "Select an organization"}</small></div>
        <label className="qms-mobile-navigation">Module
          <select value={presentedModule} disabled={busy} onChange={(event) => navigateWorkspace(event.target.value as WorkspaceId)}>
            {navigationSections.map((section) => <optgroup key={section.label} label={section.label}>
              {section.items.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
            </optgroup>)}
          </select>
        </label>
        <nav aria-label="QMS modules">
          {navigationSections.map((section) => <div className="qms-nav-section" key={section.label}>
            <p>{section.label}</p>
            {section.items.map((item) => {
              const Icon = workspaceIcons[item.id];
              return <a key={item.id} href={`#${item.hash}`} aria-current={presentedModule === item.id ? "page" : undefined} aria-disabled={busy} onClick={(event) => {
                event.preventDefault();
                if (busy) return;
                navigateWorkspace(item.id);
              }}><Icon aria-hidden="true" size={18} /><span>{item.label}</span></a>;
            })}
          </div>)}
        </nav>
        <div className="qms-sidebar-assurance"><ShieldCheck aria-hidden="true" size={17} /><span>Visible areas follow your active QMS responsibilities.</span></div>
      </aside>
      <div className="qms-app-main">
        <header className="qms-app-topbar">
          <div className="qms-topbar-location"><p>{selectedSection?.label ?? "Workspace"} / Perfect Match QMS</p><strong>{selectedItem.label}</strong></div>
          <div className="qms-topbar-actions">
            {tenants.length > 0 && <label className="tenant-select qms-topbar-tenant"><span>Organization</span><div><select aria-label="Current organization" disabled={busy} onChange={(event) => void selectTenant(event.target.value)} value={identity.current_tenant_id ?? ""}><option disabled value="">Select organization</option>{tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name} · {tenant.role}</option>)}</select><ChevronDown aria-hidden="true" size={18} /></div></label>}
            <ThemeToggle />
            <div className="user-menu"><span className="avatar"><UserRound aria-hidden="true" size={18} /></span><span><strong>{identity.display_name}</strong><small>{identity.email ?? "Verified identity"}</small></span><button aria-label="Log out" disabled={busy} onClick={() => void logout()} title="Log out" type="button"><LogOut aria-hidden="true" size={18} /></button></div>
          </div>
        </header>
        {busy && <p className="qms-context-status" role="status">Updating your organization context…</p>}
        {!current ? <div className="qms-empty-context" id="qms-active-workspace" tabIndex={-1}><ShieldCheck aria-hidden="true" size={24} /><h1>Choose an organization</h1><p>Select an active organization to open its quality workspace. If none appears, contact its administrator.</p></div> : <fieldset className="context-workspaces qms-active-workspace" id="qms-active-workspace" disabled={busy} aria-busy={busy}>
          <legend className="sr-only">{selectedItem.label}</legend>
          {presentedModule === "overview" && <WorkspaceOverview tenantName={current.name} role={current.role} sections={visibleSections} onNavigate={navigateWorkspace} />}
          {presentedModule === "actions" && <ActionCenterWorkspace key={`actions-${current.id}-${current.role}`} role={current.role} onNavigate={navigateWorkspace} />}
          {presentedModule === "organization" && <OrganizationWorkspace key={`organization-${current.id}-${current.role}`} role={current.role} />}
          {presentedModule === "permissions" && <QMSAccessWorkspace key={`qms-access-${current.id}-${current.role}`} role={current.role} userId={identity.id} onAccessDenied={() => void loadIdentity()} />}
          {presentedModule === "processes" && <ProcessWorkspace key={`processes-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} />}
          {presentedModule === "controls" && <ControlsWorkspace key={`controls-${current.id}-${current.role}-${activeTarget?.recordId ?? "register"}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} target={activeTarget} />}
          {presentedModule === "internal-audits" && <InternalAuditsWorkspace key={`internal-audits-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {presentedModule === "risks" && <RisksWorkspace key={`risks-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {presentedModule === "nonconformities" && <NonconformitiesWorkspace key={`ncr-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {presentedModule === "capa" && <CAPAWorkspace key={`capa-${current.id}-${current.role}-${activeTarget?.recordId ?? "register"}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} target={activeTarget} />}
          {presentedModule === "documents" && <DocumentsWorkspace key={`documents-${current.id}-${current.role}`} userId={identity.id} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {presentedModule === "workflows" && <WorkflowWorkspace key={`workflows-${current.id}-${current.role}-${activeTarget?.recordId ?? "register"}`} role={current.role} target={activeTarget} />}
          {presentedModule === "audit" && (canAudit ? <AuditWorkspace key={`audit-${current.id}-${current.role}`} /> : <p className="denied-state">Audit Trail access is restricted to authorized roles.</p>)}
        </fieldset>}
      </div>
    </main>
  );
}
