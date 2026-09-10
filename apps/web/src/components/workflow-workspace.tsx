"use client";

import { CheckCircle2, GitBranch, ListChecks, Plus, Rocket, Workflow } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

type Props = { role: string };
type Definition = { id: string; code: string; name: string; description: string | null; status: string };
type Version = { id: string; definition_id: string; version_number: number; status: string };
type Step = { id: string; step_key: string; name: string; step_type: string; is_start: boolean; position: number };
type Instance = { id: string; workflow_version_id: string; title: string; status: string; current_step_id: string; row_version: number };
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

export function WorkflowWorkspace({ role }: Props) {
  const canWrite = role === "owner" || role === "admin";
  const [definitions, setDefinitions] = useState<Definition[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [selected, setSelected] = useState<Definition | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [version, setVersion] = useState<Version | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [message, setMessage] = useState("");
  const [newDefinition, setNewDefinition] = useState({ code: "", name: "" });
  const [newStep, setNewStep] = useState({ step_key: "", name: "", step_type: "task", is_start: false });

  const load = useCallback(async () => {
    const [definitionResponse, instanceResponse] = await Promise.all([call("/workflows"), call("/workflow-instances")]);
    if (definitionResponse.ok) setDefinitions((await definitionResponse.json()) as Definition[]);
    if (instanceResponse.ok) setInstances((await instanceResponse.json()) as Instance[]);
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function choose(definition: Definition) {
    setSelected(definition); setVersion(null); setSteps([]);
    const response = await call(`/workflows/${definition.id}/versions`);
    if (response.ok) {
      const rows = (await response.json()) as Version[]; setVersions(rows); if (rows[0]) await chooseVersion(rows[0]);
    }
  }
  async function chooseVersion(row: Version) {
    setVersion(row);
    const response = await call(`/workflows/versions/${row.id}/steps`);
    if (response.ok) setSteps((await response.json()) as Step[]);
  }
  async function submitDefinition(event: FormEvent) {
    event.preventDefault(); setMessage("");
    const response = await call("/workflows", { method: "POST", body: JSON.stringify({ ...newDefinition, description: null }) });
    setMessage(response.ok ? "Workflow definition created." : "The definition could not be created.");
    if (response.ok) { setNewDefinition({ code: "", name: "" }); await load(); }
  }
  async function createVersion() {
    if (!selected) return;
    const response = await call(`/workflows/${selected.id}/versions`, { method: "POST" });
    if (response.ok) { const row = (await response.json()) as Version; await choose(selected); await chooseVersion(row); setMessage("Draft version created."); }
  }
  async function addStep(event: FormEvent) {
    event.preventDefault(); if (!version) return;
    const response = await call(`/workflows/versions/${version.id}/steps`, { method: "POST", body: JSON.stringify({ ...newStep, position: steps.length }) });
    if (response.ok) { setNewStep({ step_key: "", name: "", step_type: "task", is_start: false }); await chooseVersion(version); }
  }
  async function publish() {
    if (!version) return;
    const response = await call(`/workflows/versions/${version.id}/publish`, { method: "POST" });
    setMessage(response.ok ? "Version published." : "Publication validation failed. Check the graph and assignments.");
    if (response.ok && selected) await choose(selected);
  }
  return (
    <section className="workflow-workspace" aria-labelledby="workflow-heading">
      <div className="workspace-heading"><div><p className="eyebrow">Controlled operations</p><h2 id="workflow-heading"><Workflow aria-hidden="true" size={21} /> Workflow Engine</h2><p className="workspace-subtitle">Versioned approvals and tasks for this organization.</p></div><span className="status-note"><CheckCircle2 aria-hidden="true" size={16} /> {canWrite ? "Configuration access" : "Read-only access"}</span></div>
      {message && <p className="workflow-message" role="status">{message}</p>}
      <div className="workflow-grid">
        <div className="workflow-list"><h3><ListChecks aria-hidden="true" size={18} /> Definitions</h3>{definitions.length === 0 ? <p className="empty-state">No workflow definitions yet.</p> : <ul>{definitions.map((item) => <li key={item.id}><button type="button" className={selected?.id === item.id ? "selected" : ""} onClick={() => void choose(item)}><strong>{item.name}</strong><small>{item.code} · {item.status}</small></button></li>)}</ul>}
          {canWrite && <form className="workflow-form" onSubmit={(event) => void submitDefinition(event)}><h4>New definition</h4><label>Code<input required maxLength={40} value={newDefinition.code} onChange={(event) => setNewDefinition({ ...newDefinition, code: event.target.value })} /></label><label>Name<input required maxLength={160} value={newDefinition.name} onChange={(event) => setNewDefinition({ ...newDefinition, name: event.target.value })} /></label><button className="primary-action compact-action" type="submit"><Plus aria-hidden="true" size={17} /> Create definition</button></form>}
        </div>
        <div className="workflow-detail">{!selected ? <div className="empty-state"><GitBranch aria-hidden="true" size={20} /><span>Select a definition to inspect its versions.</span></div> : <><div className="detail-heading"><div><h3>{selected.name}</h3><p>{selected.code} · {selected.status}</p></div>{canWrite && <button className="secondary-action compact-action" type="button" onClick={() => void createVersion()}><Plus aria-hidden="true" size={16} /> Draft version</button>}</div><div className="version-tabs" role="tablist" aria-label="Workflow versions">{versions.map((item) => <button key={item.id} className={version?.id === item.id ? "selected" : ""} type="button" role="tab" aria-selected={version?.id === item.id} onClick={() => void chooseVersion(item)}>v{item.version_number} · {item.status}</button>)}</div>{version && <><div className="builder-heading"><h4>Version {version.version_number}</h4>{canWrite && version.status === "draft" && <button className="primary-action compact-action" type="button" onClick={() => void publish()}><Rocket aria-hidden="true" size={16} /> Publish</button>}</div><ol className="step-list">{steps.map((step) => <li key={step.id}><strong>{step.name}</strong><small>{step.step_key} · {step.step_type}{step.is_start ? " · start" : ""}</small></li>)}</ol>{canWrite && version.status === "draft" && <form className="workflow-form" onSubmit={(event) => void addStep(event)}><h4>Add step</h4><label>Key<input required maxLength={40} value={newStep.step_key} onChange={(event) => setNewStep({ ...newStep, step_key: event.target.value })} /></label><label>Name<input required maxLength={160} value={newStep.name} onChange={(event) => setNewStep({ ...newStep, name: event.target.value })} /></label><label>Type<select value={newStep.step_type} onChange={(event) => setNewStep({ ...newStep, step_type: event.target.value })}><option value="task">Task</option><option value="approval">Approval</option><option value="end">End</option></select></label><label className="check-label"><input type="checkbox" checked={newStep.is_start} onChange={(event) => setNewStep({ ...newStep, is_start: event.target.checked })} /> Start step</label><button className="secondary-action compact-action" type="submit"><Plus aria-hidden="true" size={16} /> Add step</button></form>}</>}</>}
        </div>
      </div>
      <div className="workflow-instances"><div className="assignment-heading"><h3>Instances</h3><span>{instances.length} visible</span></div>{instances.length === 0 ? <p className="empty-state">No active or completed instances.</p> : <ul className="step-list">{instances.map((item) => <li key={item.id}><strong>{item.title}</strong><small>{item.status} · step {item.current_step_id.slice(0, 8)} · version {item.row_version}</small></li>)}</ul>}</div>
    </section>
  );
}
