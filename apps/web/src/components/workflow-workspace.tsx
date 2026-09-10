"use client";

import { CheckCircle2, GitBranch, ListChecks, Plus, Rocket, Workflow } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Props = { role: string };
type Definition = { id: string; code: string; name: string; description: string | null; status: string };
type Version = { id: string; definition_id: string; version_number: number; status: string };
type Step = { id: string; step_key: string; name: string; step_type: string; is_start: boolean; position: number };
type Transition = { id: string; from_step_id: string; to_step_id: string; transition_key: string; label: string };
type Assignment = { id: string; step_id: string; target_type: string; target_user_id: string | null; target_organization_unit_id: string | null; target_application_role: string | null };
type Member = { id: string; display_name: string; role: string };
type Instance = { id: string; workflow_version_id: string; title: string; status: string; current_step_id: string; row_version: number };
type Action = { id: string; transition_key: string; label: string; to_step_id: string };
type Event = { id: string; event_type: string; occurred_at: string; actor_user_id: string; reason: string | null };
const api = "/api/identity";

function csrf(): string {
  const item = document.cookie.split("; ").find((cookie) => cookie.startsWith("pm_csrf="));
  return item ? decodeURIComponent(item.split("=").slice(1).join("=")) : "";
}

async function call(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${api}${path}`, {
    credentials: "include", ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}), ...(init?.method && init.method !== "GET" ? { "X-CSRF-Token": csrf() } : {}) },
  });
}

async function detail(response: Response, fallback: string): Promise<string> {
  try { const body = (await response.json()) as { detail?: string }; return typeof body.detail === "string" ? body.detail : fallback; } catch { return fallback; }
}

export function WorkflowWorkspace({ role }: Props) {
  const canWrite = role === "owner" || role === "admin";
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [selected, setSelected] = useState<Definition | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [version, setVersion] = useState<Version | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [transitions, setTransitions] = useState<Transition[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [actionsByInstance, setActionsByInstance] = useState<Record<string, Action[]>>({});
  const [history, setHistory] = useState<Event[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<Instance | null>(null);
  const [message, setMessage] = useState("");
  const [newDefinition, setNewDefinition] = useState({ code: "", name: "" });
  const [newStep, setNewStep] = useState({ step_key: "", name: "", step_type: "task", is_start: false });
  const [newTransition, setNewTransition] = useState({ from_step_id: "", to_step_id: "", transition_key: "", label: "" });
  const [newAssignment, setNewAssignment] = useState({ step_id: "", target_type: "application_role", target_user_id: "", target_application_role: "member" });
  const [newInstance, setNewInstance] = useState({ workflow_version_id: "", title: "", reference: "" });
  const [cancelReason, setCancelReason] = useState("");

  const load = useCallback(async () => {
    const [definitionResponse, instanceResponse, memberResponse] = await Promise.all([call("/workflows"), call("/workflow-instances"), call("/organization/members")]);
    if (definitionResponse.ok) setDefinitions((await definitionResponse.json()) as Definition[]);
    if (memberResponse.ok) setMembers((await memberResponse.json()) as Member[]);
    if (instanceResponse.ok) {
      const rows = (await instanceResponse.json()) as Instance[]; setInstances(rows);
      const pairs = await Promise.all(rows.map(async (item) => { const response = await call(`/workflow-instances/${item.id}/actions`); return [item.id, response.ok ? (await response.json()) as Action[] : []] as const; }));
      setActionsByInstance(Object.fromEntries(pairs));
    }
  }, []);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  async function choose(definition: Definition) {
    setSelected(definition); setVersion(null); setSteps([]); setTransitions([]); setAssignments([]);
    const response = await call(`/workflows/${definition.id}/versions`);
    if (response.ok) { const rows = (await response.json()) as Version[]; setVersions(rows); if (rows[0]) await chooseVersion(rows[0]); }
  }

  async function chooseVersion(row: Version) {
    setVersion(row);
    const [stepResponse, transitionResponse, assignmentResponse] = await Promise.all([call(`/workflows/versions/${row.id}/steps`), call(`/workflows/versions/${row.id}/transitions`), call(`/workflows/versions/${row.id}/assignments`)]);
    if (stepResponse.ok) setSteps((await stepResponse.json()) as Step[]);
    if (transitionResponse.ok) setTransitions((await transitionResponse.json()) as Transition[]);
    if (assignmentResponse.ok) setAssignments((await assignmentResponse.json()) as Assignment[]);
    setNewInstance((current) => ({ ...current, workflow_version_id: row.status === "published" ? row.id : current.workflow_version_id }));
  }

  async function submitDefinition(event: FormEvent) {
    event.preventDefault(); setMessage(""); const response = await call("/workflows", { method: "POST", body: JSON.stringify({ ...newDefinition, description: null }) });
    setMessage(response.ok ? "Workflow definition created." : await detail(response, "The definition could not be created.")); if (response.ok) { setNewDefinition({ code: "", name: "" }); await load(); }
  }

  async function createVersion() {
    if (!selected) return; const response = await call(`/workflows/${selected.id}/versions`, { method: "POST" });
    if (response.ok) { const row = (await response.json()) as Version; await choose(selected); await chooseVersion(row); setMessage("Draft version created."); } else setMessage(await detail(response, "The draft could not be created."));
  }

  async function addStep(event: FormEvent) {
    event.preventDefault(); if (!version) return; const response = await call(`/workflows/versions/${version.id}/steps`, { method: "POST", body: JSON.stringify({ ...newStep, position: steps.length }) });
    if (response.ok) { setNewStep({ step_key: "", name: "", step_type: "task", is_start: false }); await chooseVersion(version); } else setMessage(await detail(response, "The step could not be saved."));
  }

  async function addTransition(event: FormEvent) {
    event.preventDefault(); if (!version) return; const response = await call(`/workflows/versions/${version.id}/transitions`, { method: "POST", body: JSON.stringify(newTransition) });
    if (response.ok) { setNewTransition({ from_step_id: "", to_step_id: "", transition_key: "", label: "" }); await chooseVersion(version); } else setMessage(await detail(response, "The transition could not be saved."));
  }

  async function addAssignment(event: FormEvent) {
    event.preventDefault(); if (!version) return;
    const body = { ...newAssignment, target_user_id: newAssignment.target_type === "user" ? newAssignment.target_user_id : null, target_application_role: newAssignment.target_type === "application_role" ? newAssignment.target_application_role : null, target_organization_unit_id: null };
    const response = await call(`/workflows/versions/${version.id}/assignments`, { method: "POST", body: JSON.stringify(body) });
    if (response.ok) { setNewAssignment({ step_id: "", target_type: "application_role", target_user_id: "", target_application_role: "member" }); await chooseVersion(version); } else setMessage(await detail(response, "The assignment could not be saved."));
  }

  async function editStep(item: Step) {
    if (!version) return;
    const name = window.prompt("Step name", item.name)?.trim();
    if (!name) return;
    const response = await call(`/workflows/versions/${version.id}/steps/${item.id}`, { method: "PATCH", body: JSON.stringify({ step_key: item.step_key, name, description: null, step_type: item.step_type, is_start: item.is_start, position: item.position }) });
    setMessage(response.ok ? "Step updated." : await detail(response, "The step could not be updated.")); if (response.ok) await chooseVersion(version);
  }

  async function editTransition(item: Transition) {
    if (!version) return;
    const label = window.prompt("Transition label", item.label)?.trim();
    if (!label) return;
    const response = await call(`/workflows/versions/${version.id}/transitions/${item.id}`, { method: "PATCH", body: JSON.stringify({ from_step_id: item.from_step_id, to_step_id: item.to_step_id, transition_key: item.transition_key, label }) });
    setMessage(response.ok ? "Transition updated." : await detail(response, "The transition could not be updated.")); if (response.ok) await chooseVersion(version);
  }

  async function editAssignment(item: Assignment) {
    if (!version) return;
    const roleTarget = item.target_type === "application_role" ? window.prompt("Application role", item.target_application_role ?? "member")?.trim() : item.target_application_role;
    if (item.target_type === "application_role" && !roleTarget) return;
    const response = await call(`/workflows/versions/${version.id}/assignments/${item.id}`, { method: "PATCH", body: JSON.stringify({ step_id: item.step_id, target_type: item.target_type, target_user_id: item.target_user_id, target_organization_unit_id: item.target_organization_unit_id, target_application_role: roleTarget }) });
    setMessage(response.ok ? "Assignment updated." : await detail(response, "The assignment could not be updated.")); if (response.ok) await chooseVersion(version);
  }

  async function publish() {
    if (!version) return; const response = await call(`/workflows/versions/${version.id}/publish`, { method: "POST" });
    setMessage(response.ok ? "Version published." : await detail(response, "Publication validation failed.")); if (response.ok && selected) await choose(selected);
  }

  async function startInstance(event: FormEvent) {
    event.preventDefault(); const response = await call("/workflow-instances", { method: "POST", body: JSON.stringify(newInstance) });
    if (response.ok) { setNewInstance({ workflow_version_id: "", title: "", reference: "" }); setMessage("Instance started."); await load(); } else setMessage(await detail(response, "The instance could not be started."));
  }

  async function inspectInstance(item: Instance) {
    setSelectedInstance(item); setCancelReason(""); const response = await call(`/workflow-instances/${item.id}/history?limit=100`); if (response.ok) setHistory((await response.json()) as Event[]);
  }

  async function transitionInstance(item: Instance, action: Action) {
    const response = await call(`/workflow-instances/${item.id}/transition`, { method: "POST", body: JSON.stringify({ transition_id: action.id, expected_version: item.row_version }) });
    if (response.ok) { setMessage(`${item.title} transitioned.`); await load(); } else { const text = await detail(response, "This instance changed elsewhere. Reloaded current state."); setMessage(response.status === 409 ? `${text} Current instance state was reloaded.` : text); await load(); }
  }

  async function cancelSelected() {
    if (!selectedInstance || !cancelReason.trim()) { setMessage("A cancellation reason is required."); return; }
    const response = await call(`/workflow-instances/${selectedInstance.id}/cancel`, { method: "POST", body: JSON.stringify({ reason: cancelReason }) });
    setMessage(response.ok ? "Instance cancelled." : await detail(response, "The instance could not be cancelled.")); if (response.ok) { setCancelReason(""); await load(); await inspectInstance(selectedInstance); }
  }

  return (
    <section className="workflow-workspace" aria-labelledby="workflow-heading">
      <div className="workspace-heading"><div><p className="eyebrow">Controlled operations</p><h2 id="workflow-heading"><Workflow aria-hidden="true" size={21} /> Workflow Engine</h2><p className="workspace-subtitle">Versioned approvals and tasks for this organization.</p></div><span className="status-note"><CheckCircle2 aria-hidden="true" size={16} /> {canWrite ? "Configuration access" : "Read-only access"}</span></div>
      {message && <p className="workflow-message" role="status">{message}</p>}
      <div className="workflow-grid">
        <div className="workflow-list"><h3><ListChecks aria-hidden="true" size={18} /> Definitions</h3>{definitions.length === 0 ? <p className="empty-state">No workflow definitions yet.</p> : <ul>{definitions.map((item) => <li key={item.id}><button type="button" className={selected?.id === item.id ? "selected" : ""} onClick={() => void choose(item)}><strong>{item.name}</strong><small>{item.code} · {item.status}</small></button></li>)}</ul>}
          {canWrite && <form className="workflow-form" onSubmit={(event) => void submitDefinition(event)}><h4>New definition</h4><label>Code<input required maxLength={40} value={newDefinition.code} onChange={(event) => setNewDefinition({ ...newDefinition, code: event.target.value })} /></label><label>Name<input required maxLength={160} value={newDefinition.name} onChange={(event) => setNewDefinition({ ...newDefinition, name: event.target.value })} /></label><button className="primary-action compact-action" type="submit"><Plus aria-hidden="true" size={17} /> Create definition</button></form>}
          {version && canWrite && version.status === "draft" && <><form className="workflow-form" onSubmit={(event) => void addStep(event)}><h4>Add step</h4><label>Key<input required maxLength={40} value={newStep.step_key} onChange={(event) => setNewStep({ ...newStep, step_key: event.target.value })} /></label><label>Name<input required maxLength={160} value={newStep.name} onChange={(event) => setNewStep({ ...newStep, name: event.target.value })} /></label><label>Type<select value={newStep.step_type} onChange={(event) => setNewStep({ ...newStep, step_type: event.target.value })}><option value="task">Task</option><option value="approval">Approval</option><option value="end">End</option></select></label><label className="check-label"><input type="checkbox" checked={newStep.is_start} onChange={(event) => setNewStep({ ...newStep, is_start: event.target.checked })} /> Start step</label><button className="secondary-action compact-action" type="submit"><Plus aria-hidden="true" size={16} /> Add step</button></form><form className="workflow-form" onSubmit={(event) => void addTransition(event)}><h4>Add transition</h4><label>From<select required value={newTransition.from_step_id} onChange={(event) => setNewTransition({ ...newTransition, from_step_id: event.target.value })}><option value="">Select step</option>{steps.map((step) => <option key={step.id} value={step.id}>{step.name}</option>)}</select></label><label>To<select required value={newTransition.to_step_id} onChange={(event) => setNewTransition({ ...newTransition, to_step_id: event.target.value })}><option value="">Select step</option>{steps.map((step) => <option key={step.id} value={step.id}>{step.name}</option>)}</select></label><label>Key<input required maxLength={40} value={newTransition.transition_key} onChange={(event) => setNewTransition({ ...newTransition, transition_key: event.target.value })} /></label><label>Label<input required maxLength={160} value={newTransition.label} onChange={(event) => setNewTransition({ ...newTransition, label: event.target.value })} /></label><button className="secondary-action compact-action" type="submit"><Plus aria-hidden="true" size={16} /> Add transition</button></form></>}
        </div>
        <div className="workflow-detail">{!selected ? <div className="empty-state"><GitBranch aria-hidden="true" size={20} /><span>Select a definition to inspect its versions.</span></div> : <><div className="detail-heading"><div><h3>{selected.name}</h3><p>{selected.code} · {selected.status}</p></div>{canWrite && <button className="secondary-action compact-action" type="button" onClick={() => void createVersion()}><Plus aria-hidden="true" size={16} /> Draft version</button>}</div><div className="version-tabs" role="tablist" aria-label="Workflow versions">{versions.map((item) => <button key={item.id} className={version?.id === item.id ? "selected" : ""} type="button" role="tab" aria-selected={version?.id === item.id} onClick={() => void chooseVersion(item)}>v{item.version_number} · {item.status}</button>)}</div>{version && <><div className="builder-heading"><h4>Version {version.version_number}</h4>{canWrite && version.status === "draft" && <button className="primary-action compact-action" type="button" onClick={() => void publish()}><Rocket aria-hidden="true" size={16} /> Publish</button>}</div><ol className="step-list">{steps.map((step) => <li key={step.id}><strong>{step.name}</strong><small>{step.step_key} · {step.step_type}{step.is_start ? " · start" : ""}</small>{canWrite && version.status === "draft" && <button className="secondary-action compact-action" type="button" onClick={() => void editStep(step)}>Edit step</button>}</li>)}</ol><ul className="step-list">{transitions.map((item) => <li key={item.id}><strong>{item.label}</strong><small>{item.transition_key} · {item.from_step_id.slice(0, 8)} to {item.to_step_id.slice(0, 8)}</small>{canWrite && version.status === "draft" && <button className="secondary-action compact-action" type="button" onClick={() => void editTransition(item)}>Edit transition</button>}</li>)}</ul><h4>Assignments</h4><ul className="step-list">{assignments.map((item) => <li key={item.id}><strong>{steps.find((step) => step.id === item.step_id)?.name ?? item.step_id.slice(0, 8)}</strong><small>{item.target_type} · {item.target_user_id?.slice(0, 8) ?? item.target_application_role ?? item.target_organization_unit_id?.slice(0, 8)}</small>{canWrite && version.status === "draft" && <button className="secondary-action compact-action" type="button" onClick={() => void editAssignment(item)}>Edit assignment</button>}</li>)}</ul>{canWrite && version.status === "draft" && <form className="workflow-form" onSubmit={(event) => void addAssignment(event)}><h4>Add assignment</h4><label>Step<select required value={newAssignment.step_id} onChange={(event) => setNewAssignment({ ...newAssignment, step_id: event.target.value })}><option value="">Select step</option>{steps.filter((step) => step.step_type !== "end").map((step) => <option key={step.id} value={step.id}>{step.name}</option>)}</select></label><label>Target type<select value={newAssignment.target_type} onChange={(event) => setNewAssignment({ ...newAssignment, target_type: event.target.value })}><option value="application_role">Application role</option><option value="user">Member</option></select></label>{newAssignment.target_type === "user" ? <label>Member<select required value={newAssignment.target_user_id} onChange={(event) => setNewAssignment({ ...newAssignment, target_user_id: event.target.value })}><option value="">Select member</option>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name}</option>)}</select></label> : <label>Role<select value={newAssignment.target_application_role} onChange={(event) => setNewAssignment({ ...newAssignment, target_application_role: event.target.value })}><option value="member">Member</option><option value="admin">Admin</option><option value="owner">Owner</option></select></label>}<button className="secondary-action compact-action" type="submit"><Plus aria-hidden="true" size={16} /> Add assignment</button></form>}</>}</>}</div>
      </div>
      {canWrite && <form className="workflow-form" onSubmit={(event) => void startInstance(event)}><h3>Start instance</h3><label>Published version<select required value={newInstance.workflow_version_id} onChange={(event) => setNewInstance({ ...newInstance, workflow_version_id: event.target.value })}><option value="">Select published version</option>{versions.filter((item) => item.status === "published").map((item) => <option key={item.id} value={item.id}>v{item.version_number}</option>)}</select></label><label>Title<input required maxLength={200} value={newInstance.title} onChange={(event) => setNewInstance({ ...newInstance, title: event.target.value })} /></label><label>Reference<input maxLength={200} value={newInstance.reference} onChange={(event) => setNewInstance({ ...newInstance, reference: event.target.value })} /></label><button className="primary-action compact-action" type="submit"><Rocket aria-hidden="true" size={16} /> Start instance</button></form>}
      <div className="workflow-instances"><div className="assignment-heading"><h3>Instances</h3><span>{instances.length} visible</span></div>{instances.length === 0 ? <p className="empty-state">No active or completed instances.</p> : <ul className="step-list">{instances.map((item) => <li key={item.id}><button type="button" className="secondary-action compact-action" onClick={() => void inspectInstance(item)}>Inspect</button><strong>{item.title}</strong><small>{item.status} · step {item.current_step_id.slice(0, 8)} · version {item.row_version}</small>{item.status === "active" && role !== "auditor" && <div className="instance-actions">{(actionsByInstance[item.id] ?? []).map((action) => <button key={action.id} className="secondary-action compact-action" type="button" onClick={() => void transitionInstance(item, action)}><GitBranch aria-hidden="true" size={16} /> {action.label}</button>)}</div>}</li>)}</ul>}</div>
      {selectedInstance && <div className="workflow-instances"><div className="detail-heading"><div><h3>{selectedInstance.title}</h3><p>{selectedInstance.status} · version {selectedInstance.workflow_version_id.slice(0, 8)}</p></div></div><h4>History</h4><ul className="step-list">{history.map((event) => <li key={event.id}><strong>{event.event_type}</strong><small>{new Date(event.occurred_at).toLocaleString()}{event.reason ? ` · ${event.reason}` : ""}</small></li>)}</ul>{canWrite && selectedInstance.status === "active" && <div className="instance-actions"><input aria-label="Cancellation reason" required maxLength={500} value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="Cancellation reason" /><button className="secondary-action compact-action" type="button" onClick={() => void cancelSelected()}>Cancel instance</button></div>}</div>}
    </section>
  );
}
