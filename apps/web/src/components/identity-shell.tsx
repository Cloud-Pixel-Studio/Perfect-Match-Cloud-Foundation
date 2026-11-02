"use client";

import { AlertTriangle, Building2, ChartNoAxesCombined, ChevronDown, ClipboardCheck, FileText, FolderKanban, KeyRound, LayoutDashboard, ListChecks, LogIn, LogOut, ScrollText, ShieldCheck, UserRound, Workflow as WorkflowIcon, type LucideIcon } from "lucide-react";
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
import { type IdentityViewState, unauthenticatedState } from "../lib/identity-state";
import { workspaceFromHash, workspaceItems, workspaceSections, type WorkspaceId } from "../lib/workspace-navigation";

type Identity = {
  id: string;
  display_name: string;
  email: string | null;
  current_tenant_id: string | null;
};

type Tenant = { id: string; name: string; slug: string; role: string };
type AuditEvent = { id: string; occurred_at: string; actor_display_name: string; actor_role: string; action: string; resource_type: string; request_id: string; changed_fields: string[]; old_values: Record<string, unknown> | null; new_values: Record<string, unknown> | null };
const apiUrl = "/api/identity";
const workspaceIcons: Record<WorkspaceId, LucideIcon> = {
  overview: LayoutDashboard,
  processes: FolderKanban,
  documents: FileText,
  controls: ListChecks,
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
  const [showAudit, setShowAudit] = useState(false);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [activeModule, setActiveModule] = useState<WorkspaceId>("overview");
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
      const memberships = await fetch(`${apiUrl}/auth/tenants`, { credentials: "include" });
      if (!memberships.ok) throw new Error("memberships unavailable");
      const availableTenants = (await memberships.json()) as Tenant[];
      const role = availableTenants.find((tenant) => tenant.id === user.current_tenant_id)?.role ?? "";
      const nextContextKey = `${user.id}:${user.current_tenant_id ?? ""}:${role}`;
      if (contextKey.current !== nextContextKey) {
        contextRevision.current += 1;
        contextKey.current = nextContextKey;
        setShowAudit(false); setEvents([]); setAuditError(null);
      }
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
    const sync = () => setActiveModule(workspaceFromHash(window.location.hash));
    const frame = window.requestAnimationFrame(sync);
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    return () => { window.cancelAnimationFrame(frame); window.removeEventListener("hashchange", sync); window.removeEventListener("popstate", sync); };
  }, []);

  function navigateWorkspace(id: WorkspaceId) {
    if (busy) return;
    const item = workspaceItems.find((entry) => entry.id === id);
    if (!item) return;
    window.history.pushState(null, "", `#${item.hash}`);
    setActiveModule(id);
    window.scrollTo({ top: 0, behavior: "auto" });
    if (id === "audit" && !showAudit) void loadAudit();
  }

  async function selectTenant(tenantId: string) {
    contextRevision.current += 1;
    setShowAudit(false); setEvents([]); setAuditError(null);
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
    setShowAudit(false); setEvents([]); setAuditError(null);
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
    setView("anonymous");
    setBusy(false);
  }

  async function loadAudit() {
    const revision = contextRevision.current;
    setShowAudit(true);
    setAuditError(null);
    try {
      const response = await fetch(`${apiUrl}/audit/events?limit=50`, { credentials: "include" });
      if (revision !== contextRevision.current) return;
      if (!response.ok) { setAuditError(response.status === 403 ? "Audit Trail access is restricted to authorized roles." : "Audit Trail is unavailable."); return; }
      const result = (await response.json()) as { items: AuditEvent[] };
      if (revision === contextRevision.current) setEvents(result.items);
    } catch {
      if (revision === contextRevision.current) setAuditError("Audit Trail is unavailable.");
    }
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

  const current = tenants.find((tenant) => tenant.id === identity.current_tenant_id);
  const canAudit = ["owner", "admin", "auditor"].includes(current?.role ?? "");
  const selectedItem = workspaceItems.find((item) => item.id === activeModule) ?? workspaceItems[0];
  const selectedSection = workspaceSections.find((section) => section.items.some((item) => item.id === activeModule));
  const preferredUnitId = current ? unitByTenant[current.id] ?? "" : "";
  const onUnitChange = (unitId: string) => {
    if (current) setUnitByTenant((previous) => ({ ...previous, [current.id]: unitId }));
  };
  return (
    <main className="identity-main authenticated-main qms-app-shell">
      <a className="skip-link" href="#qms-active-workspace">Skip to active workspace</a>
      <aside className="qms-app-sidebar" aria-label="Main navigation">
        <div className="qms-sidebar-intro"><span className="qms-sidebar-kicker">Perfect Match</span><strong>Quality workspace</strong><small>{current?.name ?? "Select an organization"}</small></div>
        <label className="qms-mobile-navigation">Module
          <select value={activeModule} disabled={busy} onChange={(event) => navigateWorkspace(event.target.value as WorkspaceId)}>
            {workspaceSections.map((section) => <optgroup key={section.label} label={section.label}>
              {section.items.filter((item) => item.id !== "audit" || canAudit).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
              {!canAudit && activeModule === "audit" && section.items.some((item) => item.id === "audit") && <option value="audit" disabled>Audit trail restricted</option>}
            </optgroup>)}
          </select>
        </label>
        <nav aria-label="QMS modules">
          {workspaceSections.map((section) => <div className="qms-nav-section" key={section.label}>
            <p>{section.label}</p>
            {section.items.filter((item) => item.id !== "audit" || canAudit).map((item) => {
              const Icon = workspaceIcons[item.id];
              return <a key={item.id} href={`#${item.hash}`} aria-current={activeModule === item.id ? "page" : undefined} aria-disabled={busy} onClick={(event) => {
                event.preventDefault();
                if (busy) return;
                navigateWorkspace(item.id);
              }}><Icon aria-hidden="true" size={18} /><span>{item.label}</span></a>;
            })}
          </div>)}
        </nav>
        <div className="qms-sidebar-assurance"><ShieldCheck aria-hidden="true" size={17} /><span>Access follows your assigned responsibilities.</span></div>
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
          {activeModule === "overview" && <WorkspaceOverview tenantName={current.name} role={current.role} canAudit={canAudit} onNavigate={navigateWorkspace} />}
          {activeModule === "organization" && <OrganizationWorkspace key={`organization-${current.id}-${current.role}`} role={current.role} />}
          {activeModule === "permissions" && <QMSAccessWorkspace key={`qms-access-${current.id}-${current.role}`} role={current.role} userId={identity.id} onAccessDenied={() => void loadIdentity()} />}
          {activeModule === "processes" && <ProcessWorkspace key={`processes-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} />}
          {activeModule === "controls" && <ControlsWorkspace key={`controls-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {activeModule === "risks" && <RisksWorkspace key={`risks-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {activeModule === "nonconformities" && <NonconformitiesWorkspace key={`ncr-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {activeModule === "capa" && <CAPAWorkspace key={`capa-${current.id}-${current.role}`} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {activeModule === "documents" && <DocumentsWorkspace key={`documents-${current.id}-${current.role}`} userId={identity.id} preferredUnitId={preferredUnitId} onUnitChange={onUnitChange} onAccessDenied={() => void loadIdentity()} />}
          {activeModule === "workflows" && <WorkflowWorkspace key={`workflows-${current.id}-${current.role}`} role={current.role} />}
          {activeModule === "audit" && (canAudit ? <section className="audit-panel" aria-labelledby="audit-heading"><div className="audit-heading"><div><p className="eyebrow">Compliance history</p><h2 id="audit-heading">Audit trail</h2></div><button className="secondary-action compact-action" disabled={busy} onClick={() => void loadAudit()} type="button">Refresh history</button></div>{auditError ? <p className="denied-state">{auditError}</p> : !showAudit ? <p className="empty-state">Select refresh to load the latest history.</p> : events.length === 0 ? <p className="empty-state">No audit events for this organization.</p> : <div className="audit-list">{events.map((event) => <details className="audit-event" key={event.id}><summary><span><strong>{event.action}</strong><small>{event.actor_display_name} · {event.actor_role} · {event.resource_type}</small></span><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></summary><dl><dt>Request ID</dt><dd>{event.request_id}</dd><dt>Changed fields</dt><dd>{event.changed_fields.join(", ") || "None"}</dd><dt>Before</dt><dd>{event.old_values ? JSON.stringify(event.old_values) : "None"}</dd><dt>After</dt><dd>{event.new_values ? JSON.stringify(event.new_values) : "None"}</dd></dl></details>)}</div>}</section> : <p className="denied-state">Audit Trail access is restricted to authorized roles.</p>)}
        </fieldset>}
      </div>
    </main>
  );
}
