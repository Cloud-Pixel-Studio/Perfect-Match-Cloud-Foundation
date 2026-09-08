"use client";

import { Building2, ChevronDown, ClipboardList, LogIn, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ThemeToggle } from "./theme-toggle";
import { OrganizationWorkspace } from "./organization-workspace";
import { type IdentityViewState, unauthenticatedState } from "../lib/identity-state";

type Identity = {
  id: string;
  display_name: string;
  email: string | null;
  current_tenant_id: string | null;
};

type Tenant = { id: string; name: string; slug: string; role: string };
type AuditEvent = { id: string; occurred_at: string; actor_display_name: string; actor_role: string; action: string; resource_type: string; request_id: string; changed_fields: string[]; old_values: Record<string, unknown> | null; new_values: Record<string, unknown> | null };
const apiUrl = "/api/identity";

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
      setIdentity(user);
      setTenants((await memberships.json()) as Tenant[]);
      setView("authenticated");
    } catch {
      setView("error");
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadIdentity(), 0);
    return () => window.clearTimeout(timer);
  }, [loadIdentity]);

  async function selectTenant(tenantId: string) {
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
    setShowAudit(true);
    setAuditError(null);
    const response = await fetch(`${apiUrl}/audit/events?limit=50`, { credentials: "include" });
    if (!response.ok) { setAuditError(response.status === 403 ? "Audit Trail access is restricted to authorized roles." : "Audit Trail is unavailable."); return; }
    setEvents(((await response.json()) as { items: AuditEvent[] }).items);
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
  return (
    <main className="identity-main authenticated-main">
      <div className="authenticated-toolbar">
        <ThemeToggle />
        <div className="user-menu">
          <span className="avatar"><UserRound aria-hidden="true" size={18} /></span>
          <span><strong>{identity.display_name}</strong><small>{identity.email ?? "Verified identity"}</small></span>
          <button aria-label="Log out" disabled={busy} onClick={() => void logout()} title="Log out" type="button"><LogOut aria-hidden="true" size={18} /></button>
        </div>
      </div>
      <section className="organization-panel" aria-labelledby="organization-heading">
        <div className="organization-heading">
          <span className="security-mark"><Building2 aria-hidden="true" size={24} /></span>
          <div><p className="eyebrow">Organization context</p><h1 id="organization-heading">{current?.name ?? "Choose an organization"}</h1></div>
        </div>
        {tenants.length === 0 ? (
          <div className="empty-state"><ShieldCheck aria-hidden="true" size={22} /><div><strong>No active memberships</strong><p>Contact an authorized organization administrator.</p></div></div>
        ) : (
          <label className="tenant-select">
            <span>Current organization</span>
            <div><select aria-label="Current organization" disabled={busy} onChange={(event) => void selectTenant(event.target.value)} value={identity.current_tenant_id ?? ""}><option disabled value="">Select organization</option>{tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name} · {tenant.role}</option>)}</select><ChevronDown aria-hidden="true" size={18} /></div>
          </label>
        )}
        <div className="context-assurance"><ShieldCheck aria-hidden="true" size={18} /><span><strong>Validated server-side</strong><small>Organization access is derived from your active membership.</small></span></div>
        {canAudit && <button className="secondary-action" type="button" onClick={() => void loadAudit()}><ClipboardList aria-hidden="true" size={18} /> Audit Trail</button>}
      </section>
      {showAudit && <section className="audit-panel" aria-labelledby="audit-heading">
        <div className="audit-heading"><div><p className="eyebrow">Compliance history</p><h2 id="audit-heading">Audit Trail</h2></div><button className="icon-button" aria-label="Close Audit Trail" title="Close Audit Trail" type="button" onClick={() => setShowAudit(false)}>x</button></div>
        {auditError ? <p className="denied-state">{auditError}</p> : events.length === 0 ? <p className="empty-state">No audit events for this organization.</p> : <div className="audit-list">{events.map((event) => <details className="audit-event" key={event.id}><summary><span><strong>{event.action}</strong><small>{event.actor_display_name} · {event.actor_role} · {event.resource_type}</small></span><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></summary><dl><dt>Request ID</dt><dd>{event.request_id}</dd><dt>Changed fields</dt><dd>{event.changed_fields.join(", ") || "None"}</dd><dt>Before</dt><dd>{event.old_values ? JSON.stringify(event.old_values) : "None"}</dd><dt>After</dt><dd>{event.new_values ? JSON.stringify(event.new_values) : "None"}</dd></dl></details>)}</div>}
      </section>}
      {current && <OrganizationWorkspace role={current.role} />}
    </main>
  );
}
