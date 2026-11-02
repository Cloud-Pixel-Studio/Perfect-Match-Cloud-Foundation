"use client";

import { KeyRound, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Member = { id: string; display_name: string; role: string };
type Unit = { id: string; name: string; code: string; status: string };
type Grant = {
  id: string; user_id: string; unit_id: string; capability: string;
  status: string; created_at: string; revoked_at: string | null;
};

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
};
const api = "/api/identity";

function csrf(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

export function QMSAccessWorkspace({ role, userId, onAccessDenied }: {
  role: string; userId: string; onAccessDenied?: () => void;
}) {
  const owner = role === "owner";
  const [grants, setGrants] = useState<Grant[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [memberId, setMemberId] = useState("");
  const [unitId, setUnitId] = useState("");
  const [capability, setCapability] = useState("documents.read");
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const responses = await Promise.all([
        "/qms-access/grants", "/organization/members", "/organization/units",
      ].map((path) => fetch(`${api}${path}`, { credentials: "include", signal })));
      if (responses.some((response) => !response.ok)) throw new Error("access unavailable");
      const [nextGrants, nextMembers, nextUnits] = await Promise.all(responses.map((response) => response.json()));
      if (signal?.aborted) return;
      setGrants(nextGrants as Grant[]);
      setHistoryPage(0);
      setMembers(nextMembers as Member[]);
      setUnits(nextUnits as Unit[]);
      setState("ready");
    } catch {
      if (!signal?.aborted) setState("error");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [load]);

  const selectedMember = members.find((member) => member.id === memberId);
  const eligibleCapabilities = Object.entries(capabilities).filter(([key]) =>
    selectedMember?.role !== "auditor" || key.endsWith(".read"));
  const duplicate = grants.some((grant) => grant.status === "active" &&
    grant.user_id === memberId && grant.unit_id === unitId && grant.capability === capability);
  const validTarget = members.some((member) => member.id === memberId && member.id !== userId);
  const activeScope = units.some((unit) => unit.id === unitId && unit.status === "active");
  const lastHistoryPage = Math.max(0, Math.ceil(grants.length / 10) - 1);
  const visibleHistoryPage = Math.min(historyPage, lastHistoryPage);
  const visibleGrants = grants.slice(visibleHistoryPage * 10, visibleHistoryPage * 10 + 10);

  async function mutate(path: string, body?: object): Promise<boolean> {
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${api}${path}`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!response.ok) {
        if (response.status === 403 || response.status === 401) {
          setGrants([]); setState("error"); onAccessDenied?.();
        }
        setError(response.status === 403 ? "You no longer have permission to make this change. Refresh your access." :
          response.status === 409 ? "The grant or scope has changed. Refresh and try again." :
          response.status === 401 ? "Your session has expired. Sign in again." : "The change could not be saved. Try again.");
        return false;
      }
      await load();
      return true;
    } catch {
      setError("The service could not be reached. Your access list may need to be refreshed.");
      return false;
    } finally { setBusy(false); }
  }

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!owner || !validTarget || !activeScope || duplicate || busy) return;
    if (await mutate("/qms-access/grants", { user_id: memberId, unit_id: unitId, capability })) {
      setNotice("Access granted. The change has been recorded in the audit trail.");
    }
  }

  async function revoke(grantId: string) {
    if (!owner || busy) return;
    if (await mutate(`/qms-access/grants/${grantId}/revoke`)) {
      setConfirmId(null);
      setNotice("Access revoked. The original grant remains in the history.");
    }
  }

  return <section className="qms-access-panel" aria-labelledby="qms-access-heading">
    <div className="workspace-heading">
      <div><p className="eyebrow">People & access</p><h2 id="qms-access-heading">{owner ? "QMS permissions" : "My QMS permissions"}</h2>
        <p className="workspace-subtitle">Explicit responsibilities for each site, department or team.</p></div>
      <button className="secondary-action compact-action" aria-label="Refresh QMS access" disabled={busy || state === "loading"}
        onClick={() => void load()} type="button"><RefreshCw size={16} aria-hidden="true" /> Refresh</button>
    </div>
    <p className="qms-access-note"><ShieldCheck size={17} aria-hidden="true" /> Platform roles and purchased seats do not automatically grant QMS approval authority.</p>
    {state === "loading" && <RecordWorkspaceSkeleton label="Loading QMS permissions" />}
    {state === "error" && <p role="alert" className="denied-state">Permissions could not be loaded. Refresh to try again.</p>}
    {notice && <p role="status" className="qms-access-notice">{notice}</p>}
    {error && <p role="alert" className="denied-state">{error}</p>}
    {owner && state === "ready" && <form aria-label="Grant QMS access" className="qms-access-form" onSubmit={(event) => void create(event)}>
      <h3><KeyRound size={17} aria-hidden="true" /> Grant a responsibility</h3>
      <p>Choose another active member and an exact scope. Auditors can receive read access only.</p>
      <fieldset disabled={busy || state !== "ready"}>
        <label htmlFor="qms-member">Member<select id="qms-member" required value={memberId} onChange={(event) => {
          setMemberId(event.target.value); setCapability("documents.read");
        }}><option value="">Select a member</option>{members.filter((member) => member.id !== userId).map((member) =>
          <option key={member.id} value={member.id}>{member.display_name} · {member.role}</option>)}</select></label>
        <label htmlFor="qms-scope">Scope<select id="qms-scope" required value={unitId} onChange={(event) => setUnitId(event.target.value)}>
          <option value="">Select a site, department or team</option>{units.filter((unit) => unit.status === "active").map((unit) =>
            <option key={unit.id} value={unit.id}>{unit.name} · {unit.code}</option>)}</select></label>
        <label htmlFor="qms-capability">Responsibility<select id="qms-capability" value={capability} onChange={(event) => setCapability(event.target.value)}>
          {eligibleCapabilities.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <button className="primary-action compact-action" disabled={!validTarget || !activeScope || duplicate} type="submit">Grant access</button>
      </fieldset>
      {duplicate && <p role="status">This member already has this responsibility for the selected scope.</p>}
      {state === "ready" && (!units.some((unit) => unit.status === "active") || members.every((member) => member.id === userId)) &&
        <p>Add an active organization unit and another member before granting access.</p>}
    </form>}
    {state === "ready" && <>
      <p className="qms-history-caption">Recent grants · latest 100 records{owner ? " for this organization" : " assigned to you"}</p>
      {!grants.length ? <div className="empty-state"><ShieldCheck size={22} aria-hidden="true" /><div><strong>No QMS permissions assigned</strong>
        <p>{owner ? "Grant explicit responsibilities to active members above." : "Contact your organization owner if you need access to QMS work."}</p></div></div> :
        <div className="qms-table-scroll"><table className="qms-access-table"><caption className="visually-hidden">QMS access grants and revocation history</caption>
          <thead><tr><th scope="col">Member</th><th scope="col">Responsibility</th><th scope="col">Scope</th><th scope="col">Status</th><th scope="col">Granted</th>{owner && <th scope="col">Action</th>}</tr></thead>
          <tbody>{visibleGrants.map((grant) => {
            const scope = units.find((unit) => unit.id === grant.unit_id);
            const member = members.find((item) => item.id === grant.user_id);
            return <tr key={grant.id}><td data-label="Member">{member?.display_name ?? `Member (${grant.user_id.slice(0, 8)})`}</td>
              <td data-label="Responsibility">{capabilities[grant.capability] ?? grant.capability}</td><td data-label="Scope">{scope?.name ?? "Scope unavailable"}{scope?.status === "archived" && <small>Archived scope</small>}</td>
              <td data-label="Status"><span className={`qms-grant-status ${grant.status === "active" ? "assigned" : "revoked"}`}>{grant.status === "active" ? "Assigned" : "Revoked"}</span>
                {grant.revoked_at && <small><time dateTime={grant.revoked_at}>{new Date(grant.revoked_at).toLocaleDateString()}</time></small>}</td>
              <td data-label="Granted"><time dateTime={grant.created_at}>{new Date(grant.created_at).toLocaleDateString()}</time></td>
              {owner && <td data-label="Action">{grant.status === "active" && (confirmId === grant.id ? <div className="qms-revoke-confirm">
                <span>Revoke this responsibility?</span><button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => void revoke(grant.id)}>Confirm revoke</button>
                <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setConfirmId(null)}>Cancel</button></div> :
                <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => setConfirmId(grant.id)}>Revoke</button>)}</td>}
            </tr>;
          })}</tbody></table></div>}
      {grants.length > 10 && <nav className="document-pagination" aria-label="Permission history pages">
        <button className="secondary-action compact-action" type="button" disabled={busy || visibleHistoryPage === 0} onClick={() => setHistoryPage(visibleHistoryPage - 1)}>Previous permissions</button>
        <span>Page {visibleHistoryPage + 1} of {lastHistoryPage + 1}</span>
        <button className="secondary-action compact-action" type="button" disabled={busy || visibleHistoryPage === lastHistoryPage} onClick={() => setHistoryPage(visibleHistoryPage + 1)}>Next permissions</button>
      </nav>}
      <p className="qms-history-caption">Assigned grants apply only while the member, membership, organization and scope remain active. Document and process workflows are still in development.</p>
    </>}
  </section>;
}
