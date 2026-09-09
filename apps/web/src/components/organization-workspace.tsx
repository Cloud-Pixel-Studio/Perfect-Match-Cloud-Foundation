"use client";

import { ChevronDown, ChevronRight, Pencil, Plus, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Unit = { id: string; tenant_id: string; parent_id: string | null; unit_type: "site" | "department" | "team"; code: string; name: string; description: string | null; status: "active" | "archived" };
type Assignment = { id: string; unit_id: string; user_id: string; user_display_name: string | null; assignment_role: "member" | "lead"; is_primary: boolean; status: "active" | "inactive" };
type Member = { id: string; display_name: string; role: string };

const api = "/api/identity";
const labels: Record<Unit["unit_type"], string> = { site: "Sites", department: "Departments", team: "Teams" };

function csrfToken(): string {
  const item = document.cookie.split("; ").find((cookie) => cookie.startsWith("pm_csrf="));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : "";
}

export function OrganizationWorkspace({ role }: { role: string }) {
  const [units, setUnits] = useState<Unit[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [saving, setSaving] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [draftCode, setDraftCode] = useState("");
  const [draftParent, setDraftParent] = useState("");
  const [assignUser, setAssignUser] = useState("");
  const [assignRole, setAssignRole] = useState<"member" | "lead">("member");
  const selected = units.find((unit) => unit.id === selectedId) ?? null;
  const canEdit = role === "owner" || role === "admin";
  const visible = useMemo(() => units.filter((unit) => `${unit.name} ${unit.code}`.toLowerCase().includes(query.toLowerCase())), [query, units]);
  const selectedAssignments = assignments.filter((assignment) => assignment.unit_id === selected?.id && assignment.status === "active");

  async function load(): Promise<void> {
    try {
      const responses = await Promise.all(["units", "assignments", "members"].map((resource) => fetch(`${api}/organization/${resource}`, { credentials: "include" })));
      if (responses.some((response) => !response.ok)) throw new Error("organization unavailable");
      const nextUnits = (await responses[0].json()) as Unit[];
      setUnits(nextUnits); setAssignments((await responses[1].json()) as Assignment[]); setMembers((await responses[2].json()) as Member[]);
      const nextSelected = nextUnits.find((unit) => unit.id === selectedId) ?? nextUnits[0] ?? null;
      setSelectedId(nextSelected?.id ?? null);
      if (nextSelected) { setDraftName(nextSelected.name); setDraftCode(nextSelected.code); setDraftParent(nextSelected.parent_id ?? ""); }
      setState(nextUnits.length ? "ready" : "empty");
    } catch { setState("error"); }
  }

  // The initial load is intentionally independent of the selected unit.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, []);
  function selectUnit(unit: Unit): void { setSelectedId(unit.id); setDraftName(unit.name); setDraftCode(unit.code); setDraftParent(unit.parent_id ?? ""); }

  async function mutate(path: string, method: "POST" | "PATCH", body?: object): Promise<boolean> {
    setSaving(true);
    try {
      const response = await fetch(`${api}${path}`, { method, credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() }, body: body ? JSON.stringify(body) : undefined });
      if (!response.ok) return false;
      await load(); return true;
    } finally { setSaving(false); }
  }
  async function createSite(): Promise<void> { await mutate("/organization/units", "POST", { unit_type: "site", code: `SITE-${units.length + 1}`, name: "New site" }); }
  async function saveUnit(): Promise<void> { if (selected) await mutate(`/organization/units/${selected.id}`, "PATCH", { name: draftName, code: draftCode }); }
  async function moveUnit(): Promise<void> { if (selected) await mutate(`/organization/units/${selected.id}/move`, "POST", { parent_id: draftParent || null }); }
  async function archiveUnit(): Promise<void> { if (selected && selected.status === "active") await mutate(`/organization/units/${selected.id}/archive`, "POST"); }
  async function addAssignment(): Promise<void> { if (selected && assignUser && await mutate("/organization/assignments", "POST", { unit_id: selected.id, user_id: assignUser, assignment_role: assignRole, is_primary: false })) setAssignUser(""); }

  function children(parentId: string | null): Unit[] { return visible.filter((unit) => unit.parent_id === parentId); }
  function treeForType(parentId: string | null, type: Unit["unit_type"], depth = 0): React.ReactNode {
    return children(parentId).filter((unit) => unit.unit_type === type).map((unit) => { const hasChildren = units.some((child) => child.parent_id === unit.id); const open = expanded.has(unit.id); return <li key={unit.id} style={{ paddingInlineStart: `${depth * 16}px` }}><button className={`tree-row ${selectedId === unit.id ? "selected" : ""}`} onClick={() => selectUnit(unit)} type="button" aria-current={selectedId === unit.id ? "true" : undefined}>{hasChildren ? <span onClick={(event) => { event.stopPropagation(); setExpanded((current) => { const next = new Set(current); if (next.has(unit.id)) next.delete(unit.id); else next.add(unit.id); return next; }); }}>{open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</span> : <span className="tree-spacer" />}<span><strong>{unit.name}</strong><small>{unit.code} · {unit.unit_type} · {unit.status}</small></span></button>{open && <ul>{(["site", "department", "team"] as const).flatMap((childType) => [treeForType(unit.id, childType, depth + 1)])}</ul>}</li>; });
  }

  return <section className="organization-workspace" aria-labelledby="organization-workspace-heading"><div className="workspace-heading"><div><p className="eyebrow">PMC-03 · Product organization</p><h2 id="organization-workspace-heading">Organization</h2><p className="workspace-subtitle">Sites, departments, teams, and tenant membership assignments.</p></div>{canEdit && <button className="primary-action compact-action" disabled={saving} onClick={() => void createSite()} type="button"><Plus size={17} /> Add site</button>}</div>{state === "loading" && <p aria-live="polite">Loading organization structure...</p>}{state === "error" && <p className="denied-state" role="alert">Organization data is unavailable or access is denied.</p>}{state === "empty" && <div className="empty-state"><Users size={21} /><div><strong>No organization units yet</strong><p>{canEdit ? "Add a site to begin the tenant structure." : "An owner or administrator has not added units yet."}</p></div></div>}{(state === "ready" || state === "empty") && <div className="organization-grid"><div className="unit-browser"><label className="search-label" htmlFor="organization-search">Find a unit</label><input id="organization-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name or code" /><ul className="organization-tree">{(["site", "department", "team"] as const).map((type) => <li key={type} className="tree-group"><strong>{labels[type]}</strong><ul>{treeForType(null, type)}</ul></li>)}</ul></div><div className="unit-details">{selected ? <><div className="detail-heading"><div><p className="eyebrow">{selected.unit_type} · {selected.status}</p><h3>{selected.name}</h3><p>{selected.code}</p></div>{canEdit && <button className="icon-button" title="Edit unit" aria-label="Edit unit" onClick={() => document.getElementById("organization-name")?.focus()} type="button"><Pencil size={17} /></button>}</div>{canEdit && <div className="management-controls"><label htmlFor="organization-name">Name<input id="organization-name" value={draftName} onChange={(event) => setDraftName(event.target.value)} /></label><label htmlFor="organization-code">Code<input id="organization-code" value={draftCode} onChange={(event) => setDraftCode(event.target.value)} /></label><button className="primary-action compact-action" disabled={saving || selected.status === "archived"} onClick={() => void saveUnit()} type="button">Save unit</button><label htmlFor="organization-parent">Parent<select id="organization-parent" value={draftParent} onChange={(event) => setDraftParent(event.target.value)}><option value="">Tenant root</option>{units.filter((unit) => unit.id !== selected.id && unit.status === "active").map((unit) => <option key={unit.id} value={unit.id}>{unit.name} ({unit.unit_type})</option>)}</select></label><button className="secondary-action compact-action" disabled={saving || selected.status === "archived"} onClick={() => void moveUnit()} type="button">Move unit</button><button className="secondary-action compact-action" disabled={saving || selected.status === "archived"} onClick={() => void archiveUnit()} type="button">Archive unit</button></div>}<dl className="unit-facts"><dt>Path</dt><dd>{selected.parent_id ? units.find((unit) => unit.id === selected.parent_id)?.name : "Tenant root"}</dd><dt>Description</dt><dd>{selected.description ?? "No description"}</dd></dl><div className="assignment-heading"><h3>People</h3><span>{selectedAssignments.length} active</span></div><ul className="assignment-list">{selectedAssignments.map((assignment) => <li key={assignment.id}><Users size={16} /><span>{assignment.user_display_name ?? assignment.user_id.slice(0, 8)}<small>{assignment.assignment_role === "lead" ? "Organization Lead" : "Organization Member"}{assignment.is_primary ? " · Primary" : ""}</small></span></li>)}</ul>{canEdit && <div className="assignment-controls"><label htmlFor="organization-member">Assign member<select id="organization-member" value={assignUser} onChange={(event) => setAssignUser(event.target.value)}><option value="">Select active member</option>{members.filter((member) => !selectedAssignments.some((assignment) => assignment.user_id === member.id)).map((member) => <option key={member.id} value={member.id}>{member.display_name} ({member.role})</option>)}</select></label><label htmlFor="organization-role">Assignment role<select id="organization-role" value={assignRole} onChange={(event) => setAssignRole(event.target.value as "member" | "lead")}><option value="member">Member</option><option value="lead">Lead</option></select></label><button className="primary-action compact-action" disabled={saving || !assignUser || selected.status === "archived"} onClick={() => void addAssignment()} type="button">Assign</button></div>}<p className="role-note">Organization roles describe structure only. They do not grant application permissions.</p></> : <p className="empty-state">Select a unit to inspect its details.</p>}</div></div>}</section>;
}
