"use client";

import { Archive, Network, Plus, RefreshCw, RotateCcw, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Scope = { id: string; code: string; name: string; can_manage: boolean };
type Process = { id: string; unit_id: string; site_ids: string[]; code: string; name: string; process_type: string; department: string; description: string; inputs: string; outputs: string; status: string; row_version: number; parent_id: string | null; owner_user_id: string | null; sequence: number };
type Member = { id: string; display_name: string };
type Site = { id: string; code: string; name: string; unit_type: string; status: string };
type Draft = Pick<Process, "code" | "name" | "process_type" | "department" | "description" | "inputs" | "outputs" | "owner_user_id" | "parent_id" | "sequence" | "site_ids">;
const empty: Draft = { code: "", name: "", process_type: "core", department: "", description: "", inputs: "", outputs: "", owner_user_id: null, parent_id: null, sequence: 10, site_ids: [] };
const api = "/api/identity/processes";

export function ProcessWorkspace({ preferredUnitId, onUnitChange }: { preferredUnitId?: string; onUnitChange?: (unitId: string) => void }) {
  const [initialPreferredUnitId] = useState(preferredUnitId ?? "");
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [scope, setScope] = useState("");
  const [rows, setRows] = useState<Process[]>([]);
  const [parentCandidates, setParentCandidates] = useState<Process[]>([]);
  const [parentSearch, setParentSearch] = useState("");
  const [findingParents, setFindingParents] = useState(false);
  const parentEpoch = useRef(0);
  const [selected, setSelected] = useState<Process | null>(null);
  const [draft, setDraft] = useState<Draft>(empty);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [busy, setBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [message, setMessage] = useState("Loading process access…");
  const [confirm, setConfirm] = useState(false);
  const epoch = useRef(0);
  const canManage = scopes.some((item) => item.id === scope && item.can_manage);

  const load = useCallback(async (unit: string, pageOffset = 0, filter = "") => {
    const revision = ++epoch.current;
    setRows([]); setParentCandidates([]); ++parentEpoch.current; setFindingParents(false); setParentSearch(""); setMembers([]); setSelected(null); setDraft(empty); setConfirm(false); setBusy(true);
    try {
      const [response, directory] = await Promise.all([fetch(`${api}?unit_id=${encodeURIComponent(unit)}&limit=51&offset=${pageOffset}&search=${encodeURIComponent(filter)}`), fetch("/api/identity/organization/members?limit=100")]);
      if (!directory.ok) throw new Error("Member directory unavailable. Try refreshing.");
      const people = await directory.json() as Member[];
      if (!response.ok) throw new Error("Unable to read processes. Refresh your access.");
      const data = await response.json() as Process[];
      if (epoch.current !== revision) return false;
      setAppliedSearch(filter); setOffset(pageOffset); setHasNext(data.length > 50);
      setMembers(people); setRows(data.slice(0, 50)); setParentCandidates(data.slice(0, 50)); setMessage("");
      return true;
    } catch (error) {
      if (epoch.current === revision) setMessage(error instanceof Error ? error.message : "Service unavailable.");
      return false;
    } finally { if (epoch.current === revision) setBusy(false); }
  }, []);

  useEffect(() => {
    const requestEpoch = epoch;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void fetch(`${api}/scopes`, { signal: controller.signal }).then(async (response) => {
        if (!response.ok) throw new Error("Access unavailable.");
        const [data, organizationRows] = await Promise.all([
          response.json() as Promise<Scope[]>,
          fetch("/api/identity/organization/units?limit=100", { signal: controller.signal }).then(async (unitsResponse) => {
            if (!unitsResponse.ok) throw new Error("Site directory unavailable.");
            return await unitsResponse.json() as Site[];
          }),
        ]);
        if (controller.signal.aborted) return;
        setScopes(data); setSites(organizationRows.filter((unit) => unit.unit_type === "site" && unit.status === "active")); setMessage(data.length ? "Select an organizational unit." : "No process access assigned. Ask your tenant owner for access to a unit.");
        if (initialPreferredUnitId && data.some((item) => item.id === initialPreferredUnitId)) { setScope(initialPreferredUnitId); void load(initialPreferredUnitId); }
      }).catch(() => { if (!controller.signal.aborted) setMessage("Process access could not be loaded. Refresh the page."); })
        .finally(() => { if (!controller.signal.aborted) setInitialLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); ++requestEpoch.current; };
  }, [initialPreferredUnitId, load]);

  function choose(row: Process | null) {
    ++parentEpoch.current; setParentSearch(""); setFindingParents(false);
    setSelected(row); setDraft(row ? { code: row.code, name: row.name, process_type: row.process_type, department: row.department, description: row.description, inputs: row.inputs, outputs: row.outputs, owner_user_id: row.owner_user_id, parent_id: row.parent_id, sequence: row.sequence, site_ids: row.site_ids } : empty); setConfirm(false);
  }

  async function findParents() {
    const revision = epoch.current;
    const request = ++parentEpoch.current;
    setFindingParents(true);
    try {
      const response = await fetch(`${api}?unit_id=${encodeURIComponent(scope)}&limit=100&search=${encodeURIComponent(parentSearch)}`);
      if (!response.ok) throw new Error("Parent search unavailable. Check your access.");
      const candidates = await response.json() as Process[];
      if (revision !== epoch.current || request !== parentEpoch.current) return;
      setParentCandidates(candidates);
      setMessage(candidates.length === 100 ? "Refine the parent search to see more specific results." : candidates.length ? "Parent search updated." : "No matching parent processes.");
    } catch (error) {
      if (revision === epoch.current && request === parentEpoch.current) setMessage(error instanceof Error ? error.message : "Search unavailable.");
    } finally { if (request === parentEpoch.current) setFindingParents(false); }
  }

  async function mutate(action: "save" | "archive" | "restore") {
    const revision = epoch.current;
    const cookie = document.cookie.split("; ").find((value) => value.startsWith("pm_csrf="));
    setBusy(true); setMessage("");
    try {
      const path = selected ? `/${selected.id}${action === "save" ? "" : `/${action}`}` : "";
      const body = action !== "save" ? { expected_version: selected?.row_version } : selected ? { ...draft, expected_version: selected.row_version } : { ...draft, unit_id: scope };
      const response = await fetch(`${api}${path}`, { method: selected && action === "save" ? "PATCH" : "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" }, body: JSON.stringify(body) });
      if (revision !== epoch.current) return;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403 || response.status === 404) { setRows([]); setScopes([]); setScope(""); choose(null); }
        throw new Error(response.status === 409 ? "The record or its dependencies changed. Refresh before trying again." : "The change could not be saved. Check your access and fields.");
      }
      const refreshed = await load(scope, offset, appliedSearch);
      if (refreshed) setMessage("Process saved.");
    } catch (error) { if (revision === epoch.current) setMessage(error instanceof Error ? error.message : "Service unavailable."); }
    finally { setBusy(false); }
  }

  return <section className="process-workspace" aria-labelledby="process-title">
    <div className="workspace-heading"><div><p className="eyebrow">Process architecture</p><h2 id="process-title"><Network aria-hidden="true" size={22} /> Process register</h2><p className="workspace-subtitle">Define ownership, purpose, inputs, outputs and applicable sites.</p></div>
      {scope && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => void load(scope, offset, appliedSearch)}><RefreshCw aria-hidden="true" size={16} /> Refresh</button>}</div>
    {message && <p className="workflow-message" role="status">{message}</p>}
    {initialLoading || (busy && Boolean(scope) && rows.length === 0) ? <RecordWorkspaceSkeleton label="Loading process register" /> : <fieldset disabled={busy}>
      <div className="process-toolbar"><label>Organizational unit <select value={scope} onChange={(event) => { const value = event.target.value; setScope(value); onUnitChange?.(value); setSearch(""); if (value) void load(value); else { ++epoch.current; setRows([]); choose(null); } }}><option value="">Select a unit</option>{scopes.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>
      {scope && <form className="process-search" aria-label="Find processes" onSubmit={(event) => { event.preventDefault(); void load(scope, 0, search); }}><label>Find a process<input maxLength={160} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Code or name" /></label><button className="secondary-action compact-action" type="submit"><Search aria-hidden="true" size={16} /> Search</button></form>}
      {canManage && <button className="primary-action compact-action" type="button" disabled={!scope} onClick={() => choose(null)}><Plus aria-hidden="true" size={16} /> New process</button>}</div>
      <div className="process-grid"><aside className="process-list" aria-label="Process register"><div className="assignment-heading"><h3>Processes</h3><span>{rows.length} visible</span></div>{rows.length ? <ul>{rows.map((row) => <li key={row.id}><button className={selected?.id === row.id ? "selected" : ""} type="button" onClick={() => choose(row)}><strong>{row.code}</strong><span>{row.name}</span><small>{row.process_type} · {row.status}</small></button></li>)}</ul> : <div className="empty-state"><Network aria-hidden="true" size={20} /><span>{scope ? "No processes match this view." : "Select an organizational unit."}</span></div>}</aside>
      <div className="process-detail">{(selected || canManage) ? <form onSubmit={(event) => { event.preventDefault(); void mutate("save"); }}>
        <h3>{selected ? selected.name : "New process"}</h3>
        <fieldset disabled={!canManage || selected?.status === "archived"}>
          {(["code", "name", "department"] as const).map((key) => <label key={key}>{key}<input required={key !== "department"} maxLength={key === "code" ? 40 : 160} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>)}
          <label>Responsible person<select value={draft.owner_user_id ?? ""} onChange={(event) => setDraft({ ...draft, owner_user_id: event.target.value || null })}><option value="">Unassigned</option>{draft.owner_user_id && !members.some((member) => member.id === draft.owner_user_id) && <option value={draft.owner_user_id}>Previous responsible person (unavailable)</option>}{members.map((member) => <option key={member.id} value={member.id}>{member.display_name}</option>)}</select></label>
          <p>Responsibility does not grant system access.</p>
          <label>Applicable sites<select multiple size={Math.min(6, Math.max(3, sites.length))} value={draft.site_ids} onChange={(event) => setDraft({ ...draft, site_ids: Array.from(event.currentTarget.selectedOptions, (option) => option.value) })}>{sites.map((site) => <option key={site.id} value={site.id}>{site.code} · {site.name}</option>)}</select></label>
          <p>Choose every active site where this process applies. A process can be shared across sites in this tenant.</p>
          <label>Find a parent process<input maxLength={160} value={parentSearch} onChange={(event) => setParentSearch(event.target.value)} placeholder="Search any process in this unit" /></label>
          <button type="button" disabled={findingParents} onClick={() => void findParents()}>Find parent</button>
          <label>Parent process<select value={draft.parent_id ?? ""} onChange={(event) => setDraft({ ...draft, parent_id: event.target.value || null })}><option value="">No parent</option>{draft.parent_id && !parentCandidates.some((row) => row.id === draft.parent_id && row.status === "active" && row.id !== selected?.id) && <option value={draft.parent_id}>Current parent (not available for selection)</option>}{parentCandidates.filter((row) => row.id !== selected?.id && row.status === "active").map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}</select></label>
          <label>Display order<input type="number" min={0} max={10000} required value={draft.sequence} onChange={(event) => setDraft({ ...draft, sequence: event.target.valueAsNumber })} /></label>
          <label>Process type<select value={draft.process_type} onChange={(event) => setDraft({ ...draft, process_type: event.target.value })}>{["management", "core", "support", "other"].map((kind) => <option key={kind}>{kind}</option>)}</select></label>
          {(["description", "inputs", "outputs"] as const).map((key) => <label key={key}>{key}<textarea maxLength={4000} rows={3} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>)}
          {canManage && selected?.status !== "archived" && <button className="primary-action compact-action" type="submit">Save process</button>}
        </fieldset>
      </form> : <div className="empty-state"><Network aria-hidden="true" size={20} /><span>Select a process to inspect it.</span></div>}
      {canManage && selected && (selected.status === "archived" ? <button className="secondary-action compact-action" type="button" onClick={() => void mutate("restore")}><RotateCcw aria-hidden="true" size={16} /> Restore process</button> : confirm ? <div className="process-confirm"><p>Archive {selected.code}? Active child processes must be archived first.</p><button className="secondary-action compact-action" type="button" onClick={() => void mutate("archive")}><Archive aria-hidden="true" size={16} /> Confirm archive</button><button className="secondary-action compact-action" type="button" onClick={() => setConfirm(false)}>Cancel</button></div> : <button className="secondary-action compact-action" type="button" onClick={() => setConfirm(true)}><Archive aria-hidden="true" size={16} /> Archive process</button>)}</div></div>
      {scope && <nav className="document-pagination" aria-label="Process pages"><button className="secondary-action compact-action" type="button" disabled={offset === 0} onClick={() => void load(scope, Math.max(0, offset - 50), appliedSearch)}>Previous</button><span>Page {Math.floor(offset / 50) + 1}</span><button className="secondary-action compact-action" type="button" disabled={!hasNext} onClick={() => void load(scope, offset + 50, appliedSearch)}>Next</button></nav>}
    </fieldset>}
  </section>;
}
