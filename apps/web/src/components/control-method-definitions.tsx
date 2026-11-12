"use client";

import { useState } from "react";

type Props = { controlId: string; draft: boolean; canManage: boolean };
type Activity = {
  id: string; name: string; sequence: number; objective: string; description: string;
  why_it_matters: string; implementation_steps: string; success_criteria: string;
  activity_kind: string; readiness_required: boolean; responsible_role: string;
  expected_output: string; evidence_expectations: string; active: boolean; row_version: number;
};
type Requirement = {
  id: string; name: string; sequence: number; description: string; acceptance_criteria: string;
  evidence_type: string; mandatory: boolean; active: boolean; row_version: number;
};

function csrf(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

async function request<T>(path: string, method = "GET", body?: object): Promise<T> {
  const response = await fetch(`/api/identity${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": csrf() } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error("A control changed state. Refresh its details and try again.");
    if (response.status === 403) throw new Error("Your control permissions changed. Refresh access or contact the organization owner.");
    throw new Error("The method definitions could not be loaded or saved.");
  }
  return (await response.json()) as T;
}

export function ControlMethodDefinitions({ controlId, draft, canManage }: Props) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true); setError("");
    try {
      const [activityRows, requirementRows] = await Promise.all([
        request<Activity[]>(`/controls/${controlId}/activities?limit=100`),
        request<Requirement[]>(`/controls/${controlId}/evidence-requirements?limit=100`),
      ]);
      setActivities(activityRows); setRequirements(requirementRows); setLoaded(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The method could not be loaded."); }
    finally { setLoading(false); }
  }

  async function saveDefinition(
    event: React.FormEvent<HTMLFormElement>,
    kind: "activity" | "requirement",
  ) {
    event.preventDefault();
    if (!draft || !canManage || busy) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    const body = kind === "activity" ? {
      name: values.get("name"), sequence: Number(values.get("sequence") || 10),
      activity_kind: values.get("activity_kind"), readiness_required: values.get("readiness_required") === "on",
      responsible_role: values.get("responsible_role") || "", objective: values.get("objective") || "",
      description: values.get("description") || "", why_it_matters: values.get("why_it_matters") || "",
      implementation_steps: values.get("implementation_steps") || "", success_criteria: values.get("success_criteria") || "",
      expected_output: values.get("expected_output") || "", evidence_expectations: values.get("evidence_expectations") || "",
    } : {
      name: values.get("name"), sequence: Number(values.get("sequence") || 10),
      evidence_type: values.get("evidence_type"), mandatory: values.get("mandatory") === "on",
      description: values.get("description") || "", acceptance_criteria: values.get("acceptance_criteria") || "",
    };
    setBusy(true); setError(""); setNotice("");
    try {
      await request(
        `/controls/${controlId}/${kind === "activity" ? "activities" : "evidence-requirements"}`,
        "POST", body,
      );
      form.reset(); setNotice(kind === "activity" ? "Implementation activity added." : "Evidence requirement added.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The definition could not be saved."); }
    finally { setBusy(false); }
  }

  async function deactivate(kind: "activity" | "requirement", row: Activity | Requirement) {
    if (!draft || !canManage || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const path = kind === "activity" ? `/control-activities/${row.id}` : `/control-evidence-requirements/${row.id}`;
      await request(path, "PATCH", { expected_version: row.row_version, active: false });
      setNotice("Definition deactivated and retained in the audit history."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The definition could not be changed."); }
    finally { setBusy(false); }
  }

  return <details className="control-method-definitions" onToggle={(event) => {
    if (event.currentTarget.open && !loaded && !loading) void load();
  }}>
    <summary>Implementation method and evidence criteria</summary>
    {error && <p className="denied-state" role="alert">{error}</p>}
    {notice && <p className="qms-access-notice" role="status">{notice}</p>}
    {loading && <p role="status">Loading definitions…</p>}
    {loaded && <div className="control-method-grid">
      <section aria-labelledby={`activities-${controlId}`}>
        <h4 id={`activities-${controlId}`}>Implementation activities</h4>
        {!activities.length && <p className="control-method-empty">No activities defined.</p>}
        <ol>{activities.map((row) => <li key={row.id}>
          <div><strong>{row.sequence}. {row.name}</strong>{row.readiness_required && <span className="process-status active">Readiness</span>}</div>
          {row.objective && <p>{row.objective}</p>}
          {row.success_criteria && <small>Success: {row.success_criteria}</small>}
          {row.responsible_role && <small>Role: {row.responsible_role}</small>}
          {!row.active && <small>Inactive · retained for traceability</small>}
          {draft && canManage && row.active && <button className="secondary-action compact-action" disabled={busy} onClick={() => void deactivate("activity", row)} type="button">Deactivate</button>}
        </li>)}</ol>
        {draft && canManage && <form className="control-method-form" onSubmit={(event) => void saveDefinition(event, "activity")}>
          <h5>Add activity</h5>
          <label>Activity title<input name="name" maxLength={160} required /></label>
          <label>Order<input name="sequence" type="number" min="0" max="1000000" defaultValue="10" /></label>
          <label>Activity type<select name="activity_kind" defaultValue="qms_implementation"><option value="qms_implementation">QMS implementation</option><option value="project_administration">Project administration</option><option value="readiness_assessment">Readiness assessment</option><option value="certification_preparation">Certification preparation</option><option value="transition">Transition</option><option value="gap_remediation">Gap remediation</option><option value="other">Other</option></select></label>
          <label>Responsible role<input name="responsible_role" maxLength={160} /></label>
          <label className="control-method-wide">Objective<textarea name="objective" maxLength={4000} rows={2} /></label>
          <label className="control-method-wide">Description<textarea name="description" maxLength={4000} rows={2} /></label>
          <label className="control-method-wide">Why it matters<textarea name="why_it_matters" maxLength={4000} rows={2} /></label>
          <label className="control-method-wide">Implementation steps<textarea name="implementation_steps" maxLength={4000} rows={3} /></label>
          <label className="control-method-wide">Success criteria<textarea name="success_criteria" maxLength={4000} rows={2} /></label>
          <label className="control-method-wide">Expected output<textarea name="expected_output" maxLength={4000} rows={2} /></label>
          <label className="control-method-wide">Evidence expectations<textarea name="evidence_expectations" maxLength={4000} rows={2} /></label>
          <label className="control-method-checkbox"><input name="readiness_required" type="checkbox" defaultChecked /> Required for readiness</label>
          <button className="primary-action compact-action" disabled={busy} type="submit">Add activity</button>
        </form>}
      </section>
      <section aria-labelledby={`requirements-${controlId}`}>
        <h4 id={`requirements-${controlId}`}>Evidence requirements</h4>
        {!requirements.length && <p className="control-method-empty">No evidence requirements defined.</p>}
        <ol>{requirements.map((row) => <li key={row.id}>
          <div><strong>{row.sequence}. {row.name}</strong>{row.mandatory && <span className="process-status active">Mandatory</span>}</div>
          <small>{row.evidence_type.replaceAll("_", " ")}</small>
          {row.description && <p>{row.description}</p>}
          {row.acceptance_criteria && <small>Acceptance: {row.acceptance_criteria}</small>}
          {!row.active && <small>Inactive · retained for traceability</small>}
          {draft && canManage && row.active && <button className="secondary-action compact-action" disabled={busy} onClick={() => void deactivate("requirement", row)} type="button">Deactivate</button>}
        </li>)}</ol>
        {draft && canManage && <form className="control-method-form" onSubmit={(event) => void saveDefinition(event, "requirement")}>
          <h5>Add evidence requirement</h5>
          <label>Requirement title<input name="name" maxLength={160} required /></label>
          <label>Order<input name="sequence" type="number" min="0" max="1000000" defaultValue="10" /></label>
          <label>Evidence type<select name="evidence_type" defaultValue="record"><option value="document">Document</option><option value="record">Record</option><option value="report">Report</option><option value="approval">Approval</option><option value="system_record">System record</option><option value="meeting">Meeting</option><option value="training">Training</option><option value="metric">Metric</option><option value="other">Other</option></select></label>
          <label className="control-method-wide">Description<textarea name="description" maxLength={4000} rows={2} /></label>
          <label className="control-method-wide">Acceptance criteria<textarea name="acceptance_criteria" maxLength={4000} rows={3} /></label>
          <label className="control-method-checkbox"><input name="mandatory" type="checkbox" defaultChecked /> Mandatory</label>
          <button className="primary-action compact-action" disabled={busy} type="submit">Add requirement</button>
        </form>}
      </section>
    </div>}
  </details>;
}
