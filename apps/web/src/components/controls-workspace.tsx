"use client";

import { BadgeCheck, ChevronDown, ClipboardCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ControlMethodDefinitions } from "./control-method-definitions";
import { ControlInstanceActivities } from "./control-instance-activities";
import { ControlInstanceEvidence } from "./control-instance-evidence";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";
import type { WorkspaceTarget } from "../lib/workspace-navigation";

type Unit = { id: string; name: string; code: string; status: string };
type Process = { id: string; code: string; name: string; status: string };
type Control = {
  id: string; unit_id: string; process_id: string; code: string; name: string; objective: string;
  description: string; category: string; guidance_purpose: string; guidance_why: string;
  implementation_guidance: string; recommended_steps: string; recommended_tools: string;
  evidence_guidance: string; practical_notes: string; owner_user_id: string | null;
  state: string; row_version: number;
};
type Instance = {
  id: string; unit_id: string; process_id: string; control_id: string; code: string; name: string;
  owner_user_id: string | null; applicability: string; justification: string; target_date: string | null;
  review_date: string | null; notes: string; implementation_status: string; implementation_date: string | null;
  status: string; row_version: number;
};
const api = "/api/identity";

function ControlDefinitionFields({ control }: { control?: Control }) {
  return <>
    <label>Code<input name="code" defaultValue={control?.code ?? ""} maxLength={40} required /></label>
    <label>Name<input name="name" defaultValue={control?.name ?? ""} maxLength={160} required /></label>
    <label>Category<select name="category" defaultValue={control?.category ?? "process"}><option value="governance">Governance</option><option value="process">Process</option><option value="document_control">Document control</option><option value="evidence">Evidence</option><option value="supplier">Supplier</option><option value="training">Training</option><option value="performance">Performance</option><option value="improvement">Improvement</option><option value="other">Other</option></select></label>
    <label className="process-wide-field">Objective<textarea name="objective" defaultValue={control?.objective ?? ""} maxLength={4000} required rows={3} /></label>
    <label className="process-wide-field">Description<textarea name="description" defaultValue={control?.description ?? ""} maxLength={4000} rows={2} /></label>
    <details className="control-guidance-editor process-wide-field">
      <summary>Reusable implementation and evidence guidance</summary>
      <div className="control-guidance-fields">
        <label>Purpose<textarea name="guidance_purpose" defaultValue={control?.guidance_purpose ?? ""} maxLength={4000} rows={3} /></label>
        <label>Why this control matters<textarea name="guidance_why" defaultValue={control?.guidance_why ?? ""} maxLength={4000} rows={3} /></label>
        <label className="process-wide-field">Implementation guidance<textarea name="implementation_guidance" defaultValue={control?.implementation_guidance ?? ""} maxLength={4000} rows={4} /></label>
        <label>Recommended steps<textarea name="recommended_steps" defaultValue={control?.recommended_steps ?? ""} maxLength={4000} rows={4} /></label>
        <label>Recommended tools<textarea name="recommended_tools" defaultValue={control?.recommended_tools ?? ""} maxLength={4000} rows={4} /></label>
        <label className="process-wide-field">Evidence guidance<textarea name="evidence_guidance" defaultValue={control?.evidence_guidance ?? ""} maxLength={4000} rows={4} /></label>
        <label className="process-wide-field">Practical notes<textarea name="practical_notes" defaultValue={control?.practical_notes ?? ""} maxLength={4000} rows={3} /></label>
      </div>
    </details>
  </>;
}

function csrf(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

async function json<T>(path: string): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include" });
  if (!response.ok) throw new Error(response.status === 403 ? "access" : "load");
  return (await response.json()) as T;
}

async function mutate<T>(path: string, method: "POST" | "PATCH", body?: object): Promise<T> {
  const response = await fetch(`${api}${path}`, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error(response.status === 403 ? "access" : response.status === 409 ? "conflict" : "save");
  return (await response.json()) as T;
}

function message(error: unknown): string {
  if (error instanceof Error && error.message === "access") return "Your QMS permissions changed. Refresh your access or contact the organization owner.";
  if (error instanceof Error && error.message === "conflict") return "This record changed. Refresh the list and review the latest version.";
  return "The control workspace is unavailable. Try refreshing.";
}

export function ControlsWorkspace({ onAccessDenied, preferredUnitId, onUnitChange, target }: { onAccessDenied?: () => void; preferredUnitId?: string; onUnitChange?: (unitId: string) => void; target?: WorkspaceTarget | null }) {
  const [initialPreferredUnitId] = useState(preferredUnitId ?? "");
  const [initialTarget] = useState(target && ["control_activity", "evidence_review"].includes(target.source) ? target : null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [unitId, setUnitId] = useState("");
  const [processes, setProcesses] = useState<Process[]>([]);
  const [processId, setProcessId] = useState("");
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [controls, setControls] = useState<Control[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const canReadControls = capabilities.includes("controls.read");
  const canManageControls = capabilities.includes("controls.manage") && capabilities.includes("processes.read");
  const canReadInstances = capabilities.includes("control_instances.read");
  const canManageInstances = capabilities.includes("control_instances.manage") && canReadControls;
  const canReviewEvidence = canManageInstances && canReadInstances && capabilities.includes("evidence.review");
  const activeControls = useMemo(() => controls.filter((control) => control.state === "active"), [controls]);

  const loadScope = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await json<Unit[]>("/organization/units");
      if (signal?.aborted) return;
      setUnits(result);
      const nextUnit = result.find((unit) => unit.id === initialPreferredUnitId && unit.status === "active")?.id
        ?? result.find((unit) => unit.status === "active")?.id ?? "";
      setUnitId(nextUnit);
    } catch (cause) {
      if (!signal?.aborted) setError(message(cause));
    }
  }, [initialPreferredUnitId]);

  const loadData = useCallback(async (signal?: AbortSignal) => {
    if (!unitId) {
      setCapabilities([]); setProcesses([]); setControls([]); setInstances([]); setLoading(false);
      return;
    }
    setLoading(true); setError("");
    try {
      const effective = await json<{ unit_id: string; capabilities: string[] }>(
        `/qms-access/effective?unit_id=${encodeURIComponent(unitId)}`,
      );
      const processRows = effective.capabilities.includes("processes.read")
        ? await json<Process[]>(`/processes?unit_id=${encodeURIComponent(unitId)}&limit=100`)
        : [];
      if (signal?.aborted) return;
      setCapabilities(effective.capabilities);
      setProcesses(processRows);
      const currentProcess = initialTarget?.processId && processRows.some((process) => process.id === initialTarget.processId && process.status === "active")
        ? initialTarget.processId : processRows.some((process) => process.id === processId && process.status === "active")
          ? processId : processRows.find((process) => process.status === "active")?.id ?? "";
      setProcessId(currentProcess);
      let controlRows: Control[] = [];
      let instanceRows: Instance[] = [];
      if (effective.capabilities.includes("controls.read")) {
        const query = `/controls?unit_id=${encodeURIComponent(unitId)}${currentProcess ? `&process_id=${encodeURIComponent(currentProcess)}` : ""}&limit=100`;
        controlRows = await json<Control[]>(query);
      }
      if (effective.capabilities.includes("control_instances.read")) {
        const query = `/control-instances?unit_id=${encodeURIComponent(unitId)}${currentProcess ? `&process_id=${encodeURIComponent(currentProcess)}` : ""}&limit=100`;
        instanceRows = await json<Instance[]>(query);
        if (initialTarget && !instanceRows.some((item) => item.id === initialTarget.recordId)) {
          const requested = await json<Instance>(`/control-instances/${initialTarget.recordId}`);
          if (requested.unit_id === unitId) instanceRows = [...instanceRows, requested];
        }
        const requestedInstance = initialTarget ? instanceRows.find((item) => item.id === initialTarget.recordId) : undefined;
        if (requestedInstance && effective.capabilities.includes("controls.read") && !controlRows.some((item) => item.id === requestedInstance.control_id)) {
          controlRows = [...controlRows, await json<Control>(`/controls/${requestedInstance.control_id}`)];
        }
      }
      setControls(controlRows);
      setInstances(instanceRows);
    } catch (cause) {
      if (!signal?.aborted) {
        setError(message(cause));
        if (cause instanceof Error && cause.message === "access") onAccessDenied?.();
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [initialTarget, onAccessDenied, processId, unitId]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadScope(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [loadScope]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadData(controller.signal), 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [loadData]);

  async function save(path: string, method: "POST" | "PATCH", body: object, success: string): Promise<boolean> {
    setBusy(true); setError(""); setNotice("");
    try {
      await mutate(path, method, body);
      setNotice(success);
      await loadData();
      return true;
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && cause.message === "access") onAccessDenied?.();
      return false;
    } finally { setBusy(false); }
  }

  async function createControl(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageControls || !processId || busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const saved = await save("/controls", "POST", {
      unit_id: unitId, process_id: processId, code: data.get("code"), name: data.get("name"),
      objective: data.get("objective"), category: data.get("category"),
      description: data.get("description") || "",
      guidance_purpose: data.get("guidance_purpose") || "",
      guidance_why: data.get("guidance_why") || "",
      implementation_guidance: data.get("implementation_guidance") || "",
      recommended_steps: data.get("recommended_steps") || "",
      recommended_tools: data.get("recommended_tools") || "",
      evidence_guidance: data.get("evidence_guidance") || "",
      practical_notes: data.get("practical_notes") || "",
    }, "Control saved as a draft. Activate it after review.");
    if (saved) form.reset();
  }

  async function updateControl(event: React.FormEvent<HTMLFormElement>, control: Control) {
    event.preventDefault();
    if (!canManageControls || control.state !== "draft" || busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const saved = await save(`/controls/${control.id}`, "PATCH", {
      expected_version: control.row_version,
      code: data.get("code"), name: data.get("name"), category: data.get("category"),
      objective: data.get("objective"), description: data.get("description") || "",
      guidance_purpose: data.get("guidance_purpose") || "",
      guidance_why: data.get("guidance_why") || "",
      implementation_guidance: data.get("implementation_guidance") || "",
      recommended_steps: data.get("recommended_steps") || "",
      recommended_tools: data.get("recommended_tools") || "",
      evidence_guidance: data.get("evidence_guidance") || "",
      practical_notes: data.get("practical_notes") || "",
    }, "Draft control updated.");
    if (saved) form.reset();
  }

  async function createInstance(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManageInstances || !processId || busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const controlId = String(data.get("control_id"));
    const control = activeControls.find((item) => item.id === controlId);
    if (!control) return;
    await save(`/control-instances?unit_id=${encodeURIComponent(unitId)}&process_id=${encodeURIComponent(processId)}`, "POST", {
      control_id: controlId, code: data.get("code"), name: data.get("name"), applicability: "applicable",
    }, "Implementation record created.");
    form.reset();
  }

  async function controlAction(control: Control, action: "activate" | "retire") {
    await save(`/controls/${control.id}/${action}`, "POST", {
      expected_version: control.row_version,
    }, action === "activate" ? "Control activated." : "Control retired. Existing records are preserved.");
  }

  async function advance(instance: Instance) {
    const next = instance.implementation_status === "not_started" ? "in_progress" :
      instance.implementation_status === "in_progress" ? "under_review" :
      instance.implementation_status === "under_review" ? "implemented" : "";
    if (!next) return;
    await save(`/control-instances/${instance.id}/transition`, "POST", {
      expected_version: instance.row_version,
      target_status: next,
      decision: next === "implemented" ? "Implementation evidence reviewed" : "Implementation status advanced",
    }, next === "implemented" ? "Implementation marked complete." : "Implementation status updated.");
  }

  const unit = units.find((item) => item.id === unitId);
  const process = processes.find((item) => item.id === processId);
  const statusLabel: Record<string, string> = {
    not_started: "Not started", in_progress: "In progress", evidence_required: "Evidence required",
    under_review: "Under review", implemented: "Implemented", not_applicable: "Not applicable",
  };

  return <section className="process-panel controls-panel" aria-labelledby="controls-heading">
    <div className="workspace-heading">
      <div><p className="eyebrow">QMS controls</p><h2 id="controls-heading"><ClipboardCheck aria-hidden="true" size={22} /> Controls & implementation</h2>
        <p className="workspace-subtitle">Reusable controls are defined per process. Each implementation has its own owner, status and traceable history.</p></div>
      <button className="secondary-action compact-action" disabled={busy || loading} onClick={() => void loadData()} type="button">
        <RefreshCw aria-hidden="true" size={16} /> Refresh
      </button>
    </div>
    <div className="process-scope-picker">
      <label>Organization scope<select value={unitId} disabled={loading || busy} onChange={(event) => { setUnitId(event.target.value); onUnitChange?.(event.target.value); setProcessId(""); }}>
        <option value="">Select a scope</option>{units.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}
      </select></label>
      <label>Process<select value={processId} disabled={!unitId || loading || busy} onChange={(event) => setProcessId(event.target.value)}>
        <option value="">All processes</option>{processes.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}
      </select></label>
    </div>
    <p className="qms-access-note"><ShieldCheck aria-hidden="true" size={17} /> Rights are checked for this exact scope. A tenant owner or purchased seat receives no implementation authority automatically.</p>
    {error && <p role="alert" className="denied-state">{error}</p>}
    {notice && <p role="status" className="qms-access-notice">{notice}</p>}
    {loading && <RecordWorkspaceSkeleton label="Loading scoped controls" />}
    {!loading && !unitId && <div className="empty-state"><BadgeCheck aria-hidden="true" size={22} /><div><strong>No active scope</strong><p>Create or activate an organization unit before managing controls.</p></div></div>}
    {!loading && unitId && !canReadControls && <div className="empty-state"><ShieldCheck aria-hidden="true" size={22} /><div><strong>Control access not assigned</strong><p>Ask the organization owner for control read access in {unit?.name ?? "this scope"}.</p></div></div>}
    {!loading && canReadControls && <>
      {canManageControls && <form className="process-editor" onSubmit={(event) => void createControl(event)}>
        <h3>New control · {process?.name ?? "select one process"}</h3>
        <fieldset disabled={busy || !processId}>
          <ControlDefinitionFields />
          <button className="primary-action compact-action" disabled={!processId || busy} type="submit">Save draft</button>
        </fieldset>
      </form>}
      {!processes.length && <p className="empty-state">No active processes are visible in this scope. Read process access is required to define controls.</p>}
      {processId && !controls.length && <p className="empty-state">No controls are assigned to {process?.name ?? "this process"} yet.</p>}
      <div className="control-card-list">{controls.map((control) => {
        const implementation = instances.find((item) => item.control_id === control.id);
        const targeted = !!implementation && implementation.id === initialTarget?.recordId;
        return <details id={implementation ? `control-implementation-${implementation.id}` : undefined} className={`control-card${targeted ? " action-target-record" : ""}`} open={targeted || undefined} key={control.id}>
          <summary className="control-card-summary"><div className="control-card-heading"><span className="eyebrow">{control.code} · {control.category.replaceAll("_", " ")}</span>
            <h3>{control.name}</h3><p>{processes.find((item) => item.id === control.process_id)?.name ?? "Process"}</p></div><span className="control-card-summary-meta"><span className={`process-status ${control.state === "active" ? "active" : control.state === "retired" ? "archived" : "draft"}`}>{control.state}</span>{implementation && <span className="qms-grant-status assigned">{statusLabel[implementation.implementation_status] ?? implementation.implementation_status}</span>}<ChevronDown aria-hidden="true" size={18} /></span></summary>
          <div className="control-card-body"><p className="control-objective">{control.objective}</p>
          {control.description && <p className="control-description">{control.description}</p>}
          {[{ label: "Implementation guidance", value: control.implementation_guidance }, { label: "Purpose", value: control.guidance_purpose }, { label: "Why it matters", value: control.guidance_why }, { label: "Recommended steps", value: control.recommended_steps }, { label: "Recommended tools", value: control.recommended_tools }, { label: "Evidence guidance", value: control.evidence_guidance }, { label: "Practical notes", value: control.practical_notes }].some((item) => item.value) &&
            <details className="control-guidance-read"><summary>Implementation and evidence guidance</summary><dl>{[
              { label: "Purpose", value: control.guidance_purpose }, { label: "Why it matters", value: control.guidance_why },
              { label: "Implementation guidance", value: control.implementation_guidance }, { label: "Recommended steps", value: control.recommended_steps },
              { label: "Recommended tools", value: control.recommended_tools }, { label: "Evidence guidance", value: control.evidence_guidance },
              { label: "Practical notes", value: control.practical_notes },
            ].filter((item) => item.value).map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl></details>}
          <ControlMethodDefinitions controlId={control.id} draft={control.state === "draft"} canManage={canManageControls} />
          {canManageControls && control.state === "draft" && <details className="control-guidance-read control-edit-draft"><summary>Edit draft definition</summary><form className="process-editor" onSubmit={(event) => void updateControl(event, control)}><fieldset disabled={busy}><ControlDefinitionFields control={control} /><button className="primary-action compact-action" disabled={busy} type="submit">Save draft changes</button></fieldset></form></details>}
          <div className="control-card-actions">{canManageControls && control.state === "draft" && <button className="secondary-action compact-action" disabled={busy} onClick={() => void controlAction(control, "activate")} type="button">Activate</button>}
            {canManageControls && control.state === "active" && <button className="secondary-action compact-action" disabled={busy} onClick={() => void controlAction(control, "retire")} type="button">Retire</button>}
            {canManageInstances && control.state === "active" && !implementation && <form className="inline-instance-form" onSubmit={(event) => void createInstance(event)}>
              <input type="hidden" name="control_id" value={control.id} />
              <input aria-label={`Implementation code for ${control.name}`} name="code" defaultValue={`IMP-${control.code}`} maxLength={50} required />
              <input aria-label={`Implementation name for ${control.name}`} name="name" defaultValue={control.name} maxLength={160} required />
              <button className="secondary-action compact-action" disabled={busy} type="submit">Start implementation</button>
            </form>}
          </div>
          {implementation && <div className="control-implementation"><div><strong>{implementation.code} · {implementation.name}</strong><span className="qms-grant-status assigned">{statusLabel[implementation.implementation_status] ?? implementation.implementation_status}</span></div>
            {implementation.owner_user_id && <small>Owner assigned</small>}
            {canManageInstances && ["not_started", "in_progress", "under_review"].includes(implementation.implementation_status) &&
              <button className="secondary-action compact-action" disabled={busy} onClick={() => void advance(implementation)} type="button">{implementation.implementation_status === "under_review" ? "Mark implemented" : "Advance status"}</button>}
            {implementation.implementation_date && <small>Implemented {implementation.implementation_date}</small>}
          </div>}
          {implementation && canReadInstances && <ControlInstanceActivities
            instanceId={implementation.id} canManage={canManageInstances} busy={busy}
            targetActivityId={initialTarget?.source === "control_activity" && initialTarget.recordId === implementation.id ? initialTarget.subrecordId : undefined} />}
          {implementation && canReadInstances && <ControlInstanceEvidence
            instanceId={implementation.id} unitId={unitId} processId={processId}
            canManage={canManageInstances} canReview={canReviewEvidence} canReadDocuments={capabilities.includes("documents.read")}
            targetEvidenceId={initialTarget?.source === "evidence_review" && initialTarget.recordId === implementation.id ? initialTarget.subrecordId : undefined} />}
          {!canReadInstances && <small>Implementation status is hidden: no read access assigned.</small>}</div>
        </details>;
      })}</div>
    </>}
  </section>;
}
