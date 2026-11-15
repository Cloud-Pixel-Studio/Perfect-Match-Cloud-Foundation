"use client";

import { KeyRound, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  emptyHistoryFilters, grantMatchesFilters, historyContextMatches, matchesGrantCommand,
  parseQMSGrantPage, qmsHistoryQuery,
  type QMSGrantPage, type QMSHistoryFilters, type QMSHistoryGrant,
} from "../lib/qms-access-history";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Member = { id: string; display_name: string; role: string };
type Unit = { id: string; name: string; code: string; status: string };
type Catalogs = { members: Member[]; units: Unit[]; context: string };
type DuplicateCheck = { key: string; status: "clear" | "duplicate" | "error" };

const capabilities: Record<string, string> = {
  "documents.read": "Read documents", "documents.author": "Author documents",
  "documents.review": "Review documents", "documents.approve": "Approve documents",
  "documents.release": "Release documents", "documents.obsolete": "Obsolete documents", "evidence.read": "Read evidence",
  "evidence.create": "Create evidence", "evidence.review": "Review evidence",
  "processes.read": "Read processes", "processes.manage": "Manage processes",
  "controls.read": "Read controls", "controls.manage": "Manage controls",
  "control_instances.read": "Read control implementations", "control_instances.manage": "Manage control implementations",
  "risks.read": "Read risks and opportunities", "risks.manage": "Manage risks and opportunities",
  "risks.review": "Review risks and opportunities",
  "ncr.read": "Read nonconformities", "ncr.manage": "Manage nonconformities",
  "ncr.review": "Review and close nonconformities",
  "capa.read": "Read corrective actions", "capa.manage": "Manage corrective action drafts",
  "capa.review": "Review corrective actions",
  "audits.read": "Read internal-audit programs and schedules",
  "audits.manage": "Manage internal-audit planning",
  "audits.execute": "Internal-audit execution responsibility",
  "audits.review": "Review internal-audit programs and cancellations",
};
const api = "/api/identity";
const pageSize = 20;

class AccessError extends Error {
  constructor(public status: number) { super(`QMS access response ${status}`); }
}
class ContextError extends Error {}
const denied = (cause: unknown) => cause instanceof ContextError ||
  cause instanceof AccessError && [401, 403, 404].includes(cause.status);

function readMessage(cause: unknown): string {
  if (cause instanceof ContextError) return "The response does not match your company or identity. Refresh your access.";
  if (cause instanceof AccessError) {
    if (cause.status === 401) return "Your session has expired. Sign in again.";
    if ([403, 404].includes(cause.status)) return "These permissions are no longer available to you. Refresh your access.";
    if (cause.status === 409) return "The permission history context has changed. Refresh QMS access to start again.";
    if ([400, 422].includes(cause.status)) return "The history filters could not be applied. Correct the filters or reset them.";
  }
  return "Permission history could not be loaded. Refresh to try again.";
}

function csrf(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

async function read(path: string, signal?: AbortSignal, expectedTenant?: string): Promise<unknown> {
  const response = await fetch(api + path, { credentials: "include", cache: "no-store", signal });
  if (response.status !== 200) throw new AccessError(response.status);
  if (expectedTenant && response.headers.get("X-Tenant-ID") !== expectedTenant) throw new ContextError();
  return await response.json();
}

function validMembers(value: unknown): value is Member[] {
  return Array.isArray(value) && value.every(item => item && typeof item.id === "string" &&
    typeof item.display_name === "string" && typeof item.role === "string") &&
    new Set(value.map(item => item.id)).size === value.length;
}
function validUnits(value: unknown): value is Unit[] {
  return Array.isArray(value) && value.every(item => item && typeof item.id === "string" &&
    typeof item.name === "string" && typeof item.code === "string" && ["active", "archived"].includes(item.status)) &&
    new Set(value.map(item => item.id)).size === value.length;
}

export function QMSAccessWorkspace({ role, userId, tenantId, onAccessDenied }: {
  role: string; userId: string; tenantId?: string; onAccessDenied?: () => void;
}) {
  const owner = role === "owner";
  const context = JSON.stringify([tenantId ?? "", userId, role]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [page, setPage] = useState<{ source: string; data: QMSGrantPage } | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [memberId, setMemberId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [capability, setCapability] = useState("documents.read");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [draftFilters, setDraftFilters] = useState<QMSHistoryFilters>(emptyHistoryFilters);
  const [filters, setFilters] = useState<QMSHistoryFilters>(emptyHistoryFilters);
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [refresh, setRefresh] = useState(0);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheck | null>(null);
  const reads = useRef(0), duplicateReads = useRef(0), operations = useRef(0);
  const pending = useRef(false), blockedAtRefresh = useRef(-1);
  const callback = useRef(onAccessDenied);
  const liveContext = useRef(context);
  const cursor = cursors[cursors.length - 1];
  const query = qmsHistoryQuery(filters, cursor);
  const source = JSON.stringify([context, query, refresh]);
  const currentPage = page?.source === source ? page.data : null;
  const currentCatalogs = catalogs?.context === context ? catalogs : null;
  const members = currentCatalogs?.members ?? [];
  const units = currentCatalogs?.units ?? [];
  const selectedMember = members.find(member => member.id === memberId);
  const eligibleCapabilities = Object.entries(capabilities).filter(([key]) =>
    selectedMember?.role !== "auditor" || key.endsWith(".read") || key === "audits.execute");
  const validTarget = members.some(member => member.id === memberId && member.id !== userId);
  const activeScope = units.some(unit => unit.id === unitId && unit.status === "active");
  const validCapability = eligibleCapabilities.some(([key]) => key === capability);
  const selection = JSON.stringify([source, memberId, unitId, capability]);
  const duplicate = duplicateCheck?.key === selection && duplicateCheck.status === "duplicate";
  const targetChecked = duplicateCheck?.key === selection && duplicateCheck.status === "clear";
  const checkingTarget = owner && validTarget && activeScope && validCapability &&
    !!currentPage && state === "ready" && duplicateCheck?.key !== selection;
  const ready = state === "ready" && !!currentPage;
  const writeDisabled = busy || !ready || blocked;

  useEffect(() => { callback.current = onAccessDenied; }, [onAccessDenied]);
  useEffect(() => {
    liveContext.current = context;
    ++operations.current;
    pending.current = false;
    const timer = window.setTimeout(() => {
      setBusy(false); setBlocked(false); setNotice(""); setError(""); setConfirmId(null);
      setMemberId(""); setUnitId(""); setCapability("documents.read");
      setDraftFilters(emptyHistoryFilters); setFilters(emptyHistoryFilters); setCursors([null]);
      blockedAtRefresh.current = -1;
    }, 0);
    return () => window.clearTimeout(timer);
  }, [context]);
  useEffect(() => {
    const r = reads, d = duplicateReads, o = operations, p = pending;
    return () => { ++r.current; ++d.current; ++o.current; p.current = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController(), token = ++reads.current;
    const current = () => !controller.signal.aborted && token === reads.current;
    const timer = window.setTimeout(() => {
      setState("loading"); setPage(null); setConfirmId(null); setDuplicateCheck(null); setError("");
      const viewer = { userId, role, tenantId };
      void Promise.all([
        read(query, controller.signal),
        owner ? read("/organization/members", controller.signal, tenantId) : Promise.resolve(null),
        owner ? read("/organization/units", controller.signal, tenantId) : Promise.resolve(null),
      ]).then(([rawPage, rawMembers, rawUnits]) => {
        if (!current()) return;
        if (!historyContextMatches(rawPage, viewer)) throw new ContextError();
        const nextPage = parseQMSGrantPage(rawPage, viewer, pageSize);
        if (!nextPage || nextPage.items.some(grant => !grantMatchesFilters(grant, filters)) ||
          nextPage.next_cursor === cursor && cursor !== null ||
          owner && (!validMembers(rawMembers) || !validUnits(rawUnits))) throw new Error("Invalid QMS access response");
        setPage({ source, data: nextPage });
        if (owner) setCatalogs({ context, members: rawMembers as Member[], units: rawUnits as Unit[] });
        else setCatalogs(null);
        if (refresh > blockedAtRefresh.current) setBlocked(false);
        setState("ready");
      }).catch(cause => {
        if (!current()) return;
        setPage(null); setState("error"); setError(readMessage(cause));
        if (cause instanceof AccessError && cause.status === 409) {
          blockedAtRefresh.current = refresh; setBlocked(true);
        }
        if (denied(cause)) {
          ++duplicateReads.current; setCatalogs(null); setConfirmId(null); setBlocked(true);
          blockedAtRefresh.current = refresh; callback.current?.();
        }
      });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [context, cursor, filters, owner, query, refresh, role, source, tenantId, userId]);

  useEffect(() => {
    const controller = new AbortController(), token = ++duplicateReads.current;
    const current = () => !controller.signal.aborted && token === duplicateReads.current;
    if (!owner || !ready || !validTarget || !activeScope || !validCapability || blocked || busy) return;
    const targetFilters: QMSHistoryFilters = {
      q: "", status: "active", user_id: memberId, unit_id: unitId, capability,
    };
    const timer = window.setTimeout(() => {
      void read(qmsHistoryQuery(targetFilters, null, 1), controller.signal).then(raw => {
        if (!current()) return;
        const viewer = { userId, role, tenantId: currentPage?.tenant_id ?? tenantId };
        if (!historyContextMatches(raw, viewer)) throw new ContextError();
        const result = parseQMSGrantPage(raw, viewer, 1);
        if (!result || result.items.some(grant => !grantMatchesFilters(grant, targetFilters))) {
          throw new Error("Invalid duplicate check");
        }
        setDuplicateCheck({ key: selection, status: result.items.length ? "duplicate" : "clear" });
      }).catch(cause => {
        if (!current()) return;
        setDuplicateCheck({ key: selection, status: "error" });
        if (denied(cause)) {
          ++reads.current; setPage(null); setCatalogs(null); setConfirmId(null); setState("error");
          setError(readMessage(cause)); setBlocked(true); blockedAtRefresh.current = refresh;
          callback.current?.();
        } else if (cause instanceof AccessError && cause.status === 409) {
          setError(readMessage(cause)); setBlocked(true); blockedAtRefresh.current = refresh;
        }
      });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [activeScope, blocked, busy, capability, currentPage, memberId, owner, ready, refresh, role,
    selection, tenantId, unitId, userId, validCapability, validTarget]);

  function refreshAccess() {
    if (pending.current) return;
    setConfirmId(null); setCursors([null]); setRefresh(value => value + 1);
  }

  function applyFilters(next: QMSHistoryFilters) {
    if (pending.current) return;
    const normalized = { ...next, q: next.q.trim() };
    setDraftFilters(normalized); setFilters(normalized); setCursors([null]); setConfirmId(null);
  }

  async function mutate(action: "grant" | "revoke", grant?: QMSHistoryGrant) {
    if (!owner || writeDisabled || pending.current || !currentPage) return;
    if (action === "grant" && (!validTarget || !activeScope || !validCapability || !targetChecked)) return;
    if (action === "revoke" && (!grant || grant.status !== "active" || confirmId !== grant.id)) return;
    const snapshot = currentPage, capturedContext = context, token = ++operations.current;
    const target = grant ?? { user_id: memberId, unit_id: unitId, capability };
    const current = () => token === operations.current && liveContext.current === capturedContext;
    pending.current = true; setBusy(true); setError(""); setNotice("");
    const blockUntilRefresh = () => { setBlocked(true); blockedAtRefresh.current = refresh; };
    try {
      const response = await fetch(`${api}/qms-access/grants${action === "revoke" ? `/${grant?.id}/revoke` : ""}`, {
        method: "POST", credentials: "include", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: action === "grant" ? JSON.stringify(target) : undefined,
      });
      if (!current()) return;
      if (!response.ok) {
        if ([401, 403, 404].includes(response.status)) {
          ++reads.current; ++duplicateReads.current; setPage(null); setCatalogs(null); setConfirmId(null);
          setState("error"); blockUntilRefresh(); callback.current?.();
          setError(readMessage(new AccessError(response.status))); return;
        }
        if ([400, 422].includes(response.status)) {
          setError("The change was rejected. Check the member, scope and responsibility before trying again."); return;
        }
        blockUntilRefresh();
        setError(response.status === 409
          ? "The grant or scope has changed. Refresh QMS access and inspect the history before trying again."
          : "The save outcome is unconfirmed. Refresh QMS access and inspect the history before making another change.");
        return;
      }
      blockUntilRefresh();
      if (response.status !== (action === "grant" ? 201 : 200)) throw new Error("Unconfirmed status");
      const result: unknown = await response.json();
      if (!current()) return;
      if (!matchesGrantCommand(result, snapshot.viewer_user_id, target, action) ||
        action === "grant" && snapshot.items.some(item => item.id === result.id)) throw new Error("Unconfirmed response");
      setConfirmId(null);
      setNotice(action === "grant"
        ? "Access granted. The change has been recorded in the audit trail."
        : "Access revoked. The original grant remains in the history.");
      setCursors([null]); setRefresh(value => value + 1);
    } catch {
      if (current()) {
        blockUntilRefresh();
        setError("The save outcome is unconfirmed. Refresh QMS access and inspect the history before making another change.");
      }
    } finally {
      if (current()) { pending.current = false; setBusy(false); }
    }
  }

  const updateFilter = (key: keyof QMSHistoryFilters, value: string) => {
    setConfirmId(null); setDraftFilters(current => ({ ...current, [key]: value }));
  };
  const historyFiltered = Object.entries(filters).some(([key, value]) => key === "status" ? value !== "all" : !!value);

  return <section className="qms-access-panel" aria-labelledby="qms-access-heading" aria-busy={state === "loading" || busy}>
    <div className="workspace-heading">
      <div><p className="eyebrow">People & access</p><h2 id="qms-access-heading">{owner ? "QMS permissions" : "My QMS permissions"}</h2>
        <p className="workspace-subtitle">Explicit responsibilities for each site, department or team.</p></div>
      <button className="secondary-action compact-action" aria-label="Refresh QMS access" disabled={busy}
        onClick={refreshAccess} type="button"><RefreshCw size={16} aria-hidden="true" /> Refresh</button>
    </div>
    <p className="qms-access-note"><ShieldCheck size={17} aria-hidden="true" /> Platform roles and purchased seats do not automatically grant QMS approval authority.</p>
    {notice && <p role="status" className="qms-access-notice">{notice}</p>}
    {error && <p role="alert" className="denied-state">{error}{notice && " The saved change remains recorded; the displayed history has not been refreshed."}</p>}
    {blocked && <p className="qms-history-caption">Refresh QMS access before making another change. Check the recorded history to avoid repeating an earlier command.</p>}
    {owner && currentCatalogs && <form aria-label="Grant QMS access" className="qms-access-form" onSubmit={event => { event.preventDefault(); void mutate("grant"); }}>
      <h3><KeyRound size={17} aria-hidden="true" /> Grant a responsibility</h3>
      <p>Choose another active member and an exact scope. Auditors can receive read access or internal-audit execution responsibility. Execution screens are not available yet.</p>
      <fieldset disabled={writeDisabled}>
        <label htmlFor="qms-member">Member<select id="qms-member" required value={memberId} onChange={event => {
          setMemberId(event.target.value); setCapability("documents.read"); setConfirmId(null);
        }}><option value="">Select a member</option>{members.filter(member => member.id !== userId).map(member =>
          <option key={member.id} value={member.id}>{member.display_name} · {member.role}</option>)}</select></label>
        <label htmlFor="qms-scope">Scope<select id="qms-scope" required value={unitId} onChange={event => { setUnitId(event.target.value); setConfirmId(null); }}>
          <option value="">Select a site, department or team</option>{units.filter(unit => unit.status === "active").map(unit =>
            <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}</option>)}</select></label>
        <label htmlFor="qms-capability">Responsibility<select id="qms-capability" value={capability} onChange={event => { setCapability(event.target.value); setConfirmId(null); }}>
          {eligibleCapabilities.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <button className="primary-action compact-action" disabled={!validTarget || !activeScope || !validCapability || !targetChecked} type="submit">Grant access</button>
      </fieldset>
      {checkingTarget && <p role="status">Checking existing access for this member and scope…</p>}
      {duplicate && <p role="status">This member already has this responsibility for the selected scope.</p>}
      {duplicateCheck?.key === selection && duplicateCheck.status === "error" && <p role="status">Existing access could not be checked. Refresh QMS access before granting this responsibility.</p>}
      {(!units.some(unit => unit.status === "active") || members.every(member => member.id === userId)) &&
        <p>Add an active organization unit and another member before granting access.</p>}
    </form>}

    <div className="qms-permission-history-heading"><h3>Permission history</h3>
      <p className="qms-history-caption">{owner ? "Company responsibilities and revocations" : "Responsibilities assigned to you"} · Up to 20 records per page</p></div>
    <form aria-label="Filter permission history" className="qms-permission-filters" onSubmit={event => { event.preventDefault(); applyFilters(draftFilters); }}>
      <fieldset disabled={busy}>
        <legend className="visually-hidden">Filter permission history</legend>
        <label htmlFor="qms-history-search">Search permission history<input id="qms-history-search" type="search" maxLength={160}
          value={draftFilters.q} placeholder="Name, scope or responsibility" onChange={event => updateFilter("q", event.target.value)} /></label>
        <label htmlFor="qms-history-status">Permission status<select id="qms-history-status" value={draftFilters.status} onChange={event => updateFilter("status", event.target.value)}>
          <option value="all">All statuses</option><option value="active">Assigned</option><option value="revoked">Revoked</option></select></label>
        <label htmlFor="qms-history-capability">Filter responsibility<select id="qms-history-capability" value={draftFilters.capability} onChange={event => updateFilter("capability", event.target.value)}>
          <option value="">All responsibilities</option>{Object.entries(capabilities).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        {owner && currentCatalogs && <>
          <label htmlFor="qms-history-member">Filter member<select id="qms-history-member" value={draftFilters.user_id} onChange={event => updateFilter("user_id", event.target.value)}>
            <option value="">All members</option>{members.map(member => <option key={member.id} value={member.id}>{member.display_name}</option>)}</select></label>
          <label htmlFor="qms-history-scope">Filter scope<select id="qms-history-scope" value={draftFilters.unit_id} onChange={event => updateFilter("unit_id", event.target.value)}>
            <option value="">All scopes</option>{units.map(unit => <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}{unit.status === "archived" ? " · Archived" : ""}</option>)}</select></label>
        </>}
        <div className="qms-permission-filter-actions"><button className="secondary-action compact-action" type="submit"><Search size={15} aria-hidden="true" /> Apply filters</button>
          <button className="secondary-action compact-action" type="button" onClick={() => applyFilters(emptyHistoryFilters)}>Reset filters</button></div>
      </fieldset>
    </form>
    {state === "loading" && <RecordWorkspaceSkeleton label="Loading QMS permissions" />}
    {ready && currentPage && <>
      {!currentPage.items.length ? <div className="empty-state"><ShieldCheck size={22} aria-hidden="true" /><div><strong>{historyFiltered ? "No matching permissions" : "No QMS permissions assigned"}</strong>
        <p>{historyFiltered ? "Change or reset the filters to see other recorded responsibilities." : owner ? "Grant explicit responsibilities to active members above." : "Contact your organization owner if you need access to QMS work."}</p></div></div> :
        <div className="qms-table-scroll"><table className="qms-access-table"><caption className="visually-hidden">QMS access grants and revocation history</caption>
          <thead><tr><th scope="col">Member</th><th scope="col">Responsibility</th><th scope="col">Scope</th><th scope="col">Status</th><th scope="col">Granted</th>{owner && <th scope="col">Action</th>}</tr></thead>
          <tbody>{currentPage.items.map(grant => <tr key={grant.id}>
            <td data-label="Member">{grant.member_name ?? `Member (${grant.user_id.slice(0, 8)})`}</td>
            <td data-label="Responsibility">{capabilities[grant.capability] ?? grant.capability}</td>
            <td data-label="Scope">{grant.unit_name ?? "Scope unavailable"}{grant.unit_code && <small>{grant.unit_code}</small>}{grant.unit_status === "archived" && <small>Archived scope</small>}</td>
            <td data-label="Status"><span className={`qms-grant-status ${grant.status === "active" ? "assigned" : "revoked"}`}>{grant.status === "active" ? "Assigned" : "Revoked"}</span>
              {grant.revoked_at && <small><time dateTime={grant.revoked_at}>{new Date(grant.revoked_at).toLocaleDateString()}</time></small>}</td>
            <td data-label="Granted"><time dateTime={grant.created_at}>{new Date(grant.created_at).toLocaleDateString()}</time></td>
            {owner && <td data-label="Action">{grant.status === "active" && (confirmId === grant.id ? <div className="qms-revoke-confirm">
              <span>Revoke this responsibility?</span><button type="button" className="secondary-action compact-action" disabled={writeDisabled} onClick={() => void mutate("revoke", grant)}>Confirm revoke</button>
              <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setConfirmId(null)}>Cancel</button></div> :
              <button type="button" className="secondary-action compact-action" disabled={writeDisabled} onClick={() => setConfirmId(grant.id)}>Revoke</button>)}</td>}
          </tr>)}</tbody></table></div>}
      <nav className="document-pagination" aria-label="Permission history pages">
        <button className="secondary-action compact-action" type="button" disabled={busy || cursors.length === 1} onClick={() => { setConfirmId(null); setCursors(value => value.slice(0, -1)); }}>Previous permissions</button>
        <span>Page {cursors.length}</span>
        <button className="secondary-action compact-action" type="button" disabled={busy || !currentPage.next_cursor} onClick={() => {
          if (currentPage.next_cursor) { setConfirmId(null); setCursors(value => [...value, currentPage.next_cursor]); }
        }}>Next permissions</button>
      </nav>
    </>}
    <p className="qms-history-caption">Assigned grants apply only while the member, membership, organization and scope remain active. Each QMS workflow checks its required responsibilities separately.</p>
  </section>;
}
