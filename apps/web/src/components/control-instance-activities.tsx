"use client";

import { useCallback, useEffect, useState } from "react";

type Activity = {
  id: string; sequence: number; name: string; description: string; objective: string;
  why_it_matters: string; implementation_steps: string; success_criteria: string;
  activity_kind: string; readiness_required: boolean; responsible_role: string;
  expected_output: string; evidence_expectations: string; assigned_to_user_id: string | null;
  status: string; target_date: string | null; completion_summary: string; notes: string;
  completed_at: string | null; row_version: number;
};
type Member = { id: string; display_name: string };

const api = "/api/identity";

function csrf(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
  return cookie ? decodeURIComponent(cookie.slice("pm_csrf=".length)) : "";
}

export function ControlInstanceActivities({
  instanceId, canManage, busy,
}: { instanceId: string; canManage: boolean; busy: boolean }) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [assignees, setAssignees] = useState<Record<string, string>>({});
  const [completion, setCompletion] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${api}/control-instance-activities?instance_id=${encodeURIComponent(instanceId)}`, { credentials: "include" });
      if (!response.ok) throw new Error("load");
      setActivities(await response.json() as Activity[]);
      const memberResponse = await fetch(`${api}/organization/members?limit=100`, { credentials: "include" });
      if (memberResponse.ok) setMembers(await memberResponse.json() as Member[]);
      setError("");
    } catch {
      setError("Implementation activities could not be loaded. Refresh the workspace.");
    }
  }, [instanceId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function update(activity: Activity, body: object, transition: boolean) {
    setSaving(true); setError("");
    try {
      const response = await fetch(`${api}/control-instance-activities/${activity.id}${transition ? "/transition" : ""}`, {
        method: transition ? "POST" : "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: JSON.stringify({ expected_version: activity.row_version, ...body }),
      });
      if (!response.ok) throw new Error(response.status === 409 ? "conflict" : "save");
      await load();
    } catch (cause) {
      setError(cause instanceof Error && cause.message === "conflict"
        ? "This activity changed. Refresh and review its latest status."
        : "The activity could not be saved. Refresh the workspace and try again.");
    } finally { setSaving(false); }
  }

  function nextStates(status: string): string[] {
    return status === "not_started" ? ["in_progress"]
      : status === "in_progress" ? ["blocked", "under_review"]
      : status === "blocked" ? ["in_progress", "under_review"]
      : status === "under_review" ? ["in_progress", "completed"] : [];
  }

  const labels: Record<string, string> = {
    not_started: "Not started", in_progress: "In progress", blocked: "Blocked",
    under_review: "Under review", completed: "Completed",
  };

  return <details className="control-guidance-read control-instance-activities">
    <summary>Implementation activities <span className="qms-grant-status assigned">{activities.length}</span></summary>
    {error && <p role="alert" className="denied-state">{error}</p>}
    {!activities.length && !error && <p>No activities were defined for this control.</p>}
    <ol className="control-instance-activity-list">
      {activities.map((activity) => <li key={activity.id}>
        <div className="control-instance-activity-heading">
          <strong>{activity.sequence}. {activity.name}</strong>
          <span className="qms-grant-status assigned">{labels[activity.status] ?? activity.status}</span>
        </div>
        {activity.readiness_required && <small>Required before review and implementation</small>}
        {activity.responsible_role && <p><strong>Responsible role:</strong> {activity.responsible_role}</p>}
        {activity.objective && <p>{activity.objective}</p>}
        {activity.description && <p>{activity.description}</p>}
        {activity.implementation_steps && <p><strong>Steps:</strong> {activity.implementation_steps}</p>}
        {activity.success_criteria && <p><strong>Success criteria:</strong> {activity.success_criteria}</p>}
        {activity.expected_output && <p><strong>Expected output:</strong> {activity.expected_output}</p>}
        {activity.evidence_expectations && <p><strong>Evidence:</strong> {activity.evidence_expectations}</p>}
        {activity.completion_summary && <p><strong>Completion summary:</strong> {activity.completion_summary}</p>}
        {canManage && activity.status !== "completed" && <div className="control-instance-activity-actions">
          <label>Due date<input type="date" value={activity.target_date ?? ""} disabled={busy || saving}
            onChange={(event) => void update(activity, { target_date: event.target.value || null }, false)} /></label>
          <label>Responsible member<select value={assignees[activity.id] ?? activity.assigned_to_user_id ?? ""}
            disabled={busy || saving} onChange={(event) => setAssignees((current) => ({ ...current, [activity.id]: event.target.value }))}>
            <option value="">Unassigned</option>{members.map((member) => <option key={member.id} value={member.id}>{member.display_name}</option>)}
          </select>
            <button className="secondary-action compact-action" type="button" disabled={busy || saving}
              onClick={() => void update(activity, {
                assigned_to_user_id: (assignees[activity.id] ?? activity.assigned_to_user_id) || null,
              }, false)}>Save assignment</button>
          </label>
          {nextStates(activity.status).includes("completed") && <label>Completion summary<textarea rows={2}
            value={completion[activity.id] ?? ""} disabled={busy || saving}
            onChange={(event) => setCompletion((current) => ({ ...current, [activity.id]: event.target.value }))} /></label>}
          <div>{nextStates(activity.status).map((next) => <button className="secondary-action compact-action" key={next}
            type="button" disabled={busy || saving || (next === "completed" && !(completion[activity.id] ?? "").trim())}
            onClick={() => void update(activity, {
              target_status: next, decision: `Activity moved to ${labels[next] ?? next}`,
              ...(next === "completed" ? { completion_summary: completion[activity.id] } : {}),
            }, true)}>{next === "completed" ? "Complete activity" : next === "blocked" ? "Mark blocked" : next === "under_review" ? "Submit for review" : "Start / resume"}</button>)}</div>
        </div>}
        {activity.completed_at && <small>Completed {new Date(activity.completed_at).toLocaleDateString()}</small>}
      </li>)}
    </ol>
  </details>;
}
