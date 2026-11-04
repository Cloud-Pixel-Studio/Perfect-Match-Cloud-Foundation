"use client";

import { ClipboardCheck, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { CAPADocumentLinks } from "./capa-document-links";
import { CAPASourceTraceability } from "./capa-source-traceability";
import { CAPATraceLinks } from "./capa-trace-links";
import { FishboneCauses } from "./fishbone-causes";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";
import type { WorkspaceTarget } from "../lib/workspace-navigation";

type Unit = { id: string; code: string; name: string; status: string };
type Process = { id: string; code: string; name: string; status: string };
type Member = { id: string; display_name: string };
type Origin = { id: string; code: string; name: string; state: string };
type CAPAAction = { id: string; capa_id: string; title: string; description: string;
  owner_user_id: string; due_date: string; state: string; row_version: number;
  completed_by_user_id: string | null; completed_at: string | null;
  verified_by_user_id: string | null; verified_at: string | null; verification_notes: string;
  cancelled_by_user_id: string | null; cancelled_at: string | null; cancellation_reason: string };
type CAPAEffectivenessReview = { id: string; capa_id: string; cycle_number: number;
  decision: "effective" | "ineffective"; notes: string; reviewer_user_id: string;
  reviewed_at: string; active_action_count: number; verified_action_count: number;
  cancelled_action_count: number };
type CAPA = {
  id: string; unit_id: string; process_id: string; code: string; name: string;
  source_type: "ncr" | "risk" | "other"; source_ncr_id: string | null;
  source_risk_id: string | null; source_code: string; source_state: string;
  source_reference: string;
  problem_statement: string; owner_user_id: string | null; target_date: string | null;
  root_cause_method: string | null; state: string; row_version: number;
  analysis_data: Record<string, unknown>; analysis_summary: string;
  verified_root_cause: string; other_method_name: string;
  analysis_started_at: string | null;
  plan_summary: string; planned_by_user_id: string | null; planned_at: string | null;
  implementation_started_by_user_id: string | null; implementation_started_at: string | null;
  review_started_by_user_id: string | null; review_started_at: string | null;
  effective_by_user_id: string | null; effective_at: string | null;
  closed_by_user_id: string | null; closed_at: string | null; closure_notes: string;
  cancelled_by_user_id: string | null; cancelled_at: string | null; cancellation_reason: string;
};
const api = "/api/identity";
const pageSize = 50;
const label = (value: string) => value.replaceAll("_", " ");

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${api}${path}`, { credentials: "include", signal });
  if (!response.ok) throw new Error(String(response.status));
  return await response.json() as T;
}

function message(cause: unknown): string {
  const code = cause instanceof Error ? cause.message : "";
  if (["401", "403"].includes(code)) return "Your access changed. Refresh permissions or sign in again.";
  if (code === "404") return "The record or source is unavailable with your current access.";
  if (code === "409") return "The record changed or conflicts with its source. Refresh before saving.";
  if (code === "422") return "Review required fields and any confirmed cause's evidence and reason.";
  return "The corrective action register could not be reached. Try refreshing.";
}

export function CAPAWorkspace({ onAccessDenied, preferredUnitId, onUnitChange, target }: { onAccessDenied?: () => void; preferredUnitId?: string; onUnitChange?: (unitId: string) => void; target?: WorkspaceTarget | null }) {
  const [initialPreferredUnitId] = useState(preferredUnitId ?? "");
  const [initialTarget] = useState(target?.source === "capa" ? target : null);
  const [units, setUnits] = useState<Unit[]>([]);
  const [unitId, setUnitId] = useState("");
  const [caps, setCaps] = useState<string[]>([]);
  const [rows, setRows] = useState<CAPA[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [sourceType, setSourceType] = useState<CAPA["source_type"]>("other");
  const [processId, setProcessId] = useState("");
  const [originId, setOriginId] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [processes, setProcesses] = useState<Process[]>([]);
  const [origins, setOrigins] = useState<Origin[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [actions, setActions] = useState<CAPAAction[]>([]);
  const [reviews, setReviews] = useState<CAPAEffectivenessReview[]>([]);
  const [actionEditingId, setActionEditingId] = useState("");
  const [actionTransition, setActionTransition] = useState({ id: "", target: "" });
  const [actionPage, setActionPage] = useState({ id: "", offset: 0 });
  const [reviewPage, setReviewPage] = useState({ id: "", offset: 0 });
  const [processSearch, setProcessSearch] = useState("");
  const [originSearch, setOriginSearch] = useState("");
  const [memberSearch, setMemberSearch] = useState("");
  const [processOffset, setProcessOffset] = useState(0);
  const [originOffset, setOriginOffset] = useState(0);
  const [memberOffset, setMemberOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState({ q: "", offset: 0 });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  const epoch = useRef(0);
  const targetFocused = useRef(false);
  const selected = rows.find((row) => row.id === selectedId);
  const actionOffset = actionPage.id === selectedId ? actionPage.offset : 0;
  const reviewOffset = reviewPage.id === selectedId ? reviewPage.offset : 0;
  const canRead = caps.includes("capa.read");
  const canManage = canRead && caps.includes("capa.manage");
  const canReview = canRead && caps.includes("capa.review");
  const canCreate = canManage && caps.includes("processes.read");
  const canReadOrigin = sourceType === "other" || caps.includes(sourceType === "ncr" ? "ncr.read" : "risks.read");
  const refreshLinksParent = useCallback(() => setRefresh((value) => value + 1), []);
  const linksAccessChanged = useCallback(() => { setCaps([]); onAccessDenied?.(); }, [onAccessDenied]);

  useEffect(() => {
    const controller = new AbortController();
    if (!selectedId || !canRead) return () => controller.abort();
    void read<CAPAAction[]>(`/capas/${selectedId}/actions?limit=${pageSize}&offset=${actionOffset}`, controller.signal)
      .then(async (data) => {
        if (initialTarget?.recordId === selectedId && initialTarget.subrecordId && !data.some((item) => item.id === initialTarget.subrecordId)) {
          const requested = await read<CAPAAction>(`/capas/${selectedId}/actions/${initialTarget.subrecordId}`, controller.signal);
          data = [...data, requested];
        }
        if (!controller.signal.aborted) setActions(data);
      })
      .catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); });
    return () => controller.abort();
  }, [selectedId, selected?.row_version, actionOffset, canRead, initialTarget]);

  useEffect(() => {
    if (!initialTarget?.subrecordId || targetFocused.current || !actions.some((item) => item.id === initialTarget.subrecordId)) return;
    targetFocused.current = true;
    const timer = window.setTimeout(() => document.getElementById(`capa-action-${initialTarget.subrecordId}`)?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [actions, initialTarget]);

  useEffect(() => {
    const controller = new AbortController();
    if (!selectedId || !canRead) return () => controller.abort();
    void read<CAPAEffectivenessReview[]>(`/capas/${selectedId}/effectiveness-reviews?limit=${pageSize}&offset=${reviewOffset}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setReviews(data); })
      .catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); });
    return () => controller.abort();
  }, [selectedId, selected?.row_version, reviewOffset, canRead]);

  useEffect(() => {
    const controller = new AbortController();
    void read<Unit[]>("/organization/units?limit=100", controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      const active = data.filter((unit) => unit.status === "active");
      const nextUnit = active.find((unit) => unit.id === initialPreferredUnitId)?.id ?? active[0]?.id ?? "";
      setUnits(active); setUnitId(nextUnit);
      if (!active.length) setLoading(false);
    }).catch((cause) => { if (!controller.signal.aborted) { setError(message(cause)); setLoading(false); } });
    return () => controller.abort();
  }, [initialPreferredUnitId]);

  useEffect(() => {
    const revision = ++epoch.current;
    const controller = new AbortController();
    if (!unitId) return () => controller.abort();
    const timer = window.setTimeout(() => {
      setLoading(true); setError("");
      void read<{ capabilities: string[] }>(`/qms-access/effective?unit_id=${encodeURIComponent(unitId)}`, controller.signal)
      .then(async (access) => {
        if (controller.signal.aborted || revision !== epoch.current) return;
        setCaps(access.capabilities);
        if (!access.capabilities.includes("capa.read")) { setRows([]); setSelectedId(""); return; }
        const params = new URLSearchParams({ unit_id: unitId, q: query.q, limit: String(pageSize), offset: String(query.offset) });
        let data = await read<CAPA[]>(`/capas?${params}`, controller.signal);
        if (initialTarget && !data.some((item) => item.id === initialTarget.recordId)) {
          const requested = await read<CAPA>(`/capas/${initialTarget.recordId}`, controller.signal);
          if (requested.unit_id === unitId) data = [...data, requested];
        }
        if (controller.signal.aborted || revision !== epoch.current) return;
        setRows(data);
        setSelectedId((current) => initialTarget && data.some((item) => item.id === initialTarget.recordId)
          ? initialTarget.recordId : data.some((item) => item.id === current) ? current : data[0]?.id ?? "");
      }).catch((cause) => {
        if (controller.signal.aborted || revision !== epoch.current) return;
        setRows([]); setSelectedId(""); setError(message(cause));
        if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
      }).finally(() => { if (!controller.signal.aborted && revision === epoch.current) setLoading(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [unitId, query, refresh, onAccessDenied, initialTarget]);

  useEffect(() => {
    const controller = new AbortController();
    if (!unitId || !canCreate || !creating) return () => controller.abort();
    const params = new URLSearchParams({ unit_id: unitId, search: processSearch, limit: String(pageSize), offset: String(processOffset) });
    void read<Process[]>(`/processes?${params}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setProcesses(data); })
      .catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); });
    return () => controller.abort();
  }, [unitId, canCreate, creating, processSearch, processOffset]);

  useEffect(() => {
    const controller = new AbortController();
    if (!unitId || !creating || sourceType === "other" || !canReadOrigin) return () => controller.abort();
    const endpoint = sourceType === "ncr" ? "nonconformities" : "risks";
    const params = new URLSearchParams({ unit_id: unitId, q: originSearch, limit: String(pageSize), offset: String(originOffset) });
    void read<Origin[]>(`/${endpoint}?${params}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setOrigins(data.filter((item) => item.state !== "cancelled")); })
      .catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); });
    return () => controller.abort();
  }, [unitId, creating, sourceType, canReadOrigin, originSearch, originOffset]);

  useEffect(() => {
    const controller = new AbortController();
    if (!unitId || !canManage || (!creating && !editing && !(selected?.state === "action_planned" && actionEditingId))) return () => controller.abort();
    const params = new URLSearchParams({ search: memberSearch, limit: String(pageSize), offset: String(memberOffset) });
    void read<Member[]>(`/organization/members?${params}`, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setMembers(data); })
      .catch((cause) => { if (!controller.signal.aborted) setError(message(cause)); });
    return () => controller.abort();
  }, [unitId, canManage, creating, editing, selected?.state, actionEditingId, memberSearch, memberOffset]);

  async function save(event: React.FormEvent<HTMLFormElement>, record?: CAPA) {
    event.preventDefault();
    if (busy || !canManage || (!record && (!canCreate || !canReadOrigin || (sourceType !== "other" && !originId)))) return;
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {
      name: String(data.get("name") ?? ""),
      problem_statement: String(data.get("problem_statement") ?? ""),
      owner_user_id: ownerId || null,
      target_date: data.get("target_date") || null,
    };
    if (!record || record.state === "draft") body.root_cause_method = data.get("root_cause_method") || null;
    if (!record || record.state === "draft") body.source_reference = String(data.get("source_reference") ?? "");
    if (record) body.expected_version = record.row_version;
    else Object.assign(body, {
      unit_id: unitId, process_id: processId, code: data.get("code"), source_type: sourceType,
      source_ncr_id: sourceType === "ncr" ? originId : null,
      source_risk_id: sourceType === "risk" ? originId : null,
    });
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas${record ? `/${record.id}` : ""}`, {
        method: record ? "PATCH" : "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(String(response.status));
      const saved = await response.json() as CAPA;
      setCreating(false); setEditing(false); setSelectedId(saved.id);
      if (!record) { setSearch(saved.code); setQuery({ q: saved.code, offset: 0 }); }
      else setRefresh((current) => current + 1);
      setNotice(record?.state === "analysis" ? "CAPA details saved." : "Draft saved with its source and audit history.");
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
    } finally { setBusy(false); }
  }

  async function command(record: CAPA, path: string, method: "POST" | "PATCH", body: object, noticeText: string) {
    if (busy || !canManage) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${record.id}/${path}`, {
        method, credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(String(response.status));
      const saved = await response.json() as CAPA;
      setRows((current) => current.map((item) => item.id === saved.id ? saved : item));
      setNotice(noticeText);
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
    } finally { setBusy(false); }
  }

  function analysisEditor(record: CAPA) {
    const data = record.analysis_data;
    const saved = (key: string) => typeof data[key] === "string" ? data[key] as string : "";
    const dimensions = ["what", "where", "when", "extent"];
    const attributes = ["observed", "not_observed", "distinction", "change"];
    return <form className="ncr-editor" key={`analysis-${record.id}-${record.row_version}`} onSubmit={(event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const analysis_data: Record<string, unknown> = {};
      if (record.root_cause_method === "5why") for (let number = 1; number <= 5; number++) analysis_data[`why${number}`] = String(form.get(`why${number}`) ?? "");
      if (record.root_cause_method === "fishbone") {
        try { Object.assign(analysis_data, JSON.parse(String(form.get("fishbone_data") ?? "{}"))); }
        catch { setError("Fishbone causes could not be read. Review the form before saving."); return; }
      }
      if (record.root_cause_method === "is_is_not") for (const dimension of dimensions) analysis_data[dimension] = Object.fromEntries(attributes.map((attribute) => [attribute, String(form.get(`${dimension}.${attribute}`) ?? "")]));
      void command(record, "analysis", "PATCH", {
        expected_version: record.row_version, analysis_data,
        analysis_summary: String(form.get("analysis_summary") ?? ""),
        verified_root_cause: String(form.get("verified_root_cause") ?? ""),
        other_method_name: String(form.get("other_method_name") ?? ""),
      }, "Root cause analysis saved with an audit record.");
    }}><h4>{label(record.root_cause_method ?? "")} analysis</h4><fieldset className="ncr-editor-content" disabled={busy || !canManage}>
      <p className="qms-history-caption">The method and source are locked. Save your findings as the investigation progresses.</p>
      <div className="ncr-form-grid">
        {record.root_cause_method === "5why" && [1, 2, 3, 4, 5].map((number) => <label className="ncr-wide" key={number}>Why {number}<textarea name={`why${number}`} defaultValue={saved(`why${number}`)} maxLength={1000} rows={2} /></label>)}
        {record.root_cause_method === "fishbone" && <FishboneCauses data={data} disabled={busy || !canManage} />}
        {record.root_cause_method === "is_is_not" && dimensions.map((dimension) => <fieldset className="ncr-form-section ncr-wide" key={dimension}><legend>{label(dimension)}</legend><div className="ncr-form-grid">{attributes.map((attribute) => {
          const value = data[dimension];
          const text = typeof value === "object" && value !== null && attribute in value ? (value as Record<string, unknown>)[attribute] : "";
          return <label key={attribute}>{label(attribute)}<textarea name={`${dimension}.${attribute}`} defaultValue={typeof text === "string" ? text : ""} maxLength={1000} rows={2} /></label>;
        })}</div></fieldset>)}
        {record.root_cause_method === "other" && <label className="ncr-wide">Method name<input name="other_method_name" defaultValue={record.other_method_name} maxLength={160} /></label>}
        <label className="ncr-wide">Analysis summary<textarea name="analysis_summary" defaultValue={record.analysis_summary} maxLength={4000} rows={3} /></label>
        <label className="ncr-wide">Verified root cause<textarea name="verified_root_cause" defaultValue={record.verified_root_cause} maxLength={4000} rows={3} /></label>
      </div>{canManage && <div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Save analysis</button></div>}
    </fieldset></form>;
  }

  function planEditor(record: CAPA) {
    return <form className="ncr-editor" key={`plan-${record.id}-${record.row_version}`} onSubmit={(event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      void command(record, "plan/start", "POST", {
        expected_version: record.row_version,
        plan_summary: String(form.get("plan_summary") ?? ""),
      }, "Action planning started and the verified investigation was locked.");
    }}><h4>Start action planning</h4><fieldset className="ncr-editor-content" disabled={busy || !canManage}><p className="qms-history-caption">Save the investigation first. The selected method, analysis summary and verified root cause must be complete before this step. Starting the plan locks the investigation.</p><label className="ncr-wide">Plan scope and intended correction<textarea name="plan_summary" required maxLength={4000} rows={3} /></label>{canManage && <div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Start action plan</button></div>}</fieldset></form>;
  }

  async function saveAction(event: React.FormEvent<HTMLFormElement>, record: CAPA, action?: CAPAAction) {
    event.preventDefault();
    if (busy || !canManage) return;
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {
      expected_capa_version: record.row_version,
      title: String(data.get("title") ?? ""),
      description: String(data.get("description") ?? ""),
      owner_user_id: String(data.get("owner_user_id") ?? ""),
      due_date: String(data.get("due_date") ?? ""),
    };
    if (action) body.expected_action_version = action.row_version;
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${record.id}/actions${action ? `/${action.id}` : ""}`, {
        method: action ? "PATCH" : "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(String(response.status));
      const updated = await read<CAPA>(`/capas/${record.id}`);
      const nextOffset = action ? actionOffset : 0;
      const nextActions = await read<CAPAAction[]>(`/capas/${record.id}/actions?limit=${pageSize}&offset=${nextOffset}`);
      setRows((current) => current.map((item) => item.id === updated.id ? updated : item));
      setActions(nextActions); setActionPage({ id: record.id, offset: nextOffset }); setActionEditingId("");
      setNotice(action ? "Action updated with a new version and audit record." : "Action added to the plan with an audit record.");
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
    } finally { setBusy(false); }
  }

  async function transitionAction(record: CAPA, action: CAPAAction, target: string, notes = "") {
    if (busy || !canRead) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${record.id}/actions/${action.id}/transition`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify({
          expected_capa_version: record.row_version,
          expected_action_version: action.row_version,
          target_state: target,
          verification_notes: target === "verified" ? notes : "",
          cancellation_reason: target === "cancelled" ? notes : "",
        }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const updated = await read<CAPA>(`/capas/${record.id}`);
      const nextActions = await read<CAPAAction[]>(`/capas/${record.id}/actions?limit=${pageSize}&offset=${actionOffset}`);
      setRows((current) => current.map((item) => item.id === updated.id ? updated : item));
      setActions(nextActions); setActionTransition({ id: "", target: "" });
      setNotice(`Action marked ${label(target)} with a new version and audit record.`);
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
    } finally { setBusy(false); }
  }

  function transitionForm(record: CAPA, action: CAPAAction) {
    if (actionTransition.id !== action.id || !["verified", "cancelled"].includes(actionTransition.target)) return null;
    return <form onSubmit={(event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      void transitionAction(record, action, actionTransition.target, String(data.get("reason") ?? ""));
    }}><fieldset className="ncr-editor-content" disabled={busy}><label>{actionTransition.target === "verified" ? "Verification notes" : "Cancellation reason"}<textarea name="reason" required maxLength={actionTransition.target === "verified" ? 4000 : 500} rows={3} /></label><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Confirm {label(actionTransition.target)}</button><button className="secondary-action compact-action" type="button" onClick={() => setActionTransition({ id: "", target: "" })}>Cancel</button></div></fieldset></form>;
  }

  async function saveEffectivenessReview(event: React.FormEvent<HTMLFormElement>, record: CAPA) {
    event.preventDefault();
    if (busy || !canReview) return;
    const data = new FormData(event.currentTarget);
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${record.id}/effectiveness-reviews`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify({
          expected_version: record.row_version,
          decision: String(data.get("decision") ?? ""),
          notes: String(data.get("notes") ?? ""),
        }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const updated = await read<CAPA>(`/capas/${record.id}`);
      const nextReviews = await read<CAPAEffectivenessReview[]>(`/capas/${record.id}/effectiveness-reviews?limit=${pageSize}`);
      setRows((current) => current.map((item) => item.id === updated.id ? updated : item));
      setReviews(nextReviews); setReviewPage({ id: record.id, offset: 0 });
      setNotice(updated.state === "effective" ? "Effectiveness confirmed and recorded." : "Ineffective result recorded. Add or correct actions in the plan.");
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
    } finally { setBusy(false); }
  }

  async function saveClosure(event: React.FormEvent<HTMLFormElement>, record: CAPA) {
    event.preventDefault();
    if (busy || !canReview) return;
    const data = new FormData(event.currentTarget);
    setBusy(true); setError(""); setNotice("");
    try {
      const cookie = document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="));
      const response = await fetch(`${api}/capas/${record.id}/close`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": cookie ? decodeURIComponent(cookie.slice(8)) : "" },
        body: JSON.stringify({ expected_version: record.row_version, closure_notes: String(data.get("closure_notes") ?? "") }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const updated = await response.json() as CAPA;
      setRows((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice("Corrective action closed with a recorded decision.");
    } catch (cause) {
      setError(message(cause));
      if (cause instanceof Error && ["401", "403"].includes(cause.message)) { setCaps([]); onAccessDenied?.(); }
    } finally { setBusy(false); }
  }

  function reviewPanel(record: CAPA) {
    const visibleReviews = reviews.filter((item) => item.capa_id === record.id);
    return <section className="ncr-editor" aria-label="Effectiveness review"><p className="eyebrow">Effectiveness</p><h4>Review history</h4>
      {visibleReviews.length ? <ol className="ncr-record-list capa-action-list">{visibleReviews.map((item) => <li key={item.id}><div className="ncr-list-heading"><strong>Cycle {item.cycle_number}</strong><span className="process-status">{label(item.decision)}</span></div><p>{item.notes}</p><small>{new Date(item.reviewed_at).toLocaleString()} · {item.active_action_count} active · {item.verified_action_count} verified · {item.cancelled_action_count} cancelled</small></li>)}</ol> : <p className="qms-history-caption">No effectiveness decision has been recorded.</p>}
      <nav className="ncr-pagination" aria-label="Effectiveness review pages"><button type="button" disabled={busy || reviewOffset === 0} onClick={() => setReviewPage({ id: record.id, offset: Math.max(0, reviewOffset - pageSize) })}>Previous</button><span>Page {Math.floor(reviewOffset / pageSize) + 1}</span><button type="button" disabled={busy || visibleReviews.length < pageSize} onClick={() => setReviewPage({ id: record.id, offset: reviewOffset + pageSize })}>Next</button></nav>
      {record.state === "effectiveness_review" && canReview && <form onSubmit={(event) => void saveEffectivenessReview(event, record)}><fieldset className="ncr-editor-content" disabled={busy}><p className="qms-history-caption">The reviewer must be independent of everyone who completed an action.</p><label>Decision<select name="decision" required><option value="effective">Effective</option><option value="ineffective">Ineffective — return to action planning</option></select></label><label>Assessment notes<textarea name="notes" required maxLength={4000} rows={4} /></label><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Record effectiveness</button></div></fieldset></form>}
      {record.state === "effective" && canReview && <form onSubmit={(event) => void saveClosure(event, record)}><fieldset className="ncr-editor-content" disabled={busy}><label>Closure notes<textarea name="closure_notes" required maxLength={4000} rows={4} /></label><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">Close corrective action</button></div></fieldset></form>}
      {record.state === "closed" && <div><h4>Closure</h4><p>{record.closure_notes}</p><small>Closed {record.closed_at ? new Date(record.closed_at).toLocaleString() : ""}</small></div>}
    </section>;
  }

  function cancelPanel(record: CAPA) {
    if (record.state === "cancelled") return <section className="ncr-editor" aria-label="Cancellation"><h4>Cancelled</h4><p>{record.cancellation_reason}</p><small>{record.cancelled_at ? new Date(record.cancelled_at).toLocaleString() : ""}</small></section>;
    if (!canReview || record.state === "closed") return null;
    return <details className="ncr-editor"><summary>Cancel corrective action</summary><form onSubmit={(event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      void command(record, "cancel", "POST", {
        expected_version: record.row_version,
        reason: String(data.get("reason") ?? ""),
      }, "Corrective action cancelled with a recorded reason.");
    }}><fieldset className="ncr-editor-content" disabled={busy}><label>Reason for cancellation<textarea name="reason" required maxLength={500} rows={3} /></label><div className="ncr-form-actions"><button className="secondary-action compact-action" type="submit">Confirm cancellation</button></div></fieldset></form></details>;
  }

  function actionPanel(record: CAPA) {
    const visibleActions = actions.filter((item) => item.capa_id === record.id);
    const action = visibleActions.find((item) => item.id === actionEditingId);
    return <section className="ncr-editor" aria-label="Action plan register"><div className="ncr-detail-heading"><div><p className="eyebrow">Plan execution</p><h4>Actions</h4></div>{canManage && record.state === "action_planned" && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => setActionEditingId(actionEditingId === "new" ? "" : "new")}>{actionEditingId === "new" ? "Cancel" : "Add action"}</button>}</div>
      {visibleActions.length ? <ul className="ncr-record-list capa-action-list">{visibleActions.map((item) => <li id={`capa-action-${item.id}`} className={initialTarget?.subrecordId === item.id ? "action-target-record" : undefined} tabIndex={-1} key={item.id}><div className="ncr-list-heading"><strong>{item.title}</strong><span className="process-status">{label(item.state)}</span></div><p>{item.description}</p><small>Due {item.due_date} · {members.find((member) => member.id === item.owner_user_id)?.display_name ?? "Assigned owner"}</small>{item.verified_at && <small>Verified {new Date(item.verified_at).toLocaleString()} · {item.verification_notes}</small>}{item.cancelled_at && <small>Cancelled {new Date(item.cancelled_at).toLocaleString()} · {item.cancellation_reason}</small>}{canManage && record.state === "action_planned" && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => setActionEditingId(actionEditingId === item.id ? "" : item.id)}>{actionEditingId === item.id ? "Cancel" : "Edit action"}</button>}{record.state === "implementation" && <div className="ncr-form-actions">{canManage && item.state === "open" && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => void transitionAction(record, item, "in_progress")}>Start</button>}{canManage && ["open", "in_progress"].includes(item.state) && <button className="primary-action compact-action" type="button" disabled={busy} onClick={() => void transitionAction(record, item, "completed")}>Mark completed</button>}{canReview && item.state === "completed" && <button className="primary-action compact-action" type="button" disabled={busy} onClick={() => setActionTransition({ id: item.id, target: "verified" })}>Verify</button>}{canReview && ["open", "in_progress", "completed"].includes(item.state) && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => setActionTransition({ id: item.id, target: "cancelled" })}>Cancel action</button>}</div>}{transitionForm(record, item)}</li>)}</ul> : <p className="qms-history-caption">No actions have been assigned yet.</p>}
      <nav className="ncr-pagination" aria-label="Action pages"><button type="button" disabled={busy || actionOffset === 0} onClick={() => setActionPage({ id: record.id, offset: Math.max(0, actionOffset - pageSize) })}>Previous</button><span>Page {Math.floor(actionOffset / pageSize) + 1}</span><button type="button" disabled={busy || visibleActions.length < pageSize} onClick={() => setActionPage({ id: record.id, offset: actionOffset + pageSize })}>Next</button></nav>
      {canManage && record.state === "action_planned" && actionEditingId && <form key={action?.id ?? "new-action"} onSubmit={(event) => void saveAction(event, record, action)}><fieldset className="ncr-editor-content" disabled={busy}><div className="ncr-form-grid"><label className="ncr-wide">Action title<input name="title" defaultValue={action?.title ?? ""} maxLength={160} required /></label><label className="ncr-wide">Description<textarea name="description" defaultValue={action?.description ?? ""} maxLength={4000} rows={3} required /></label><label>Responsible person<select name="owner_user_id" defaultValue={action?.owner_user_id ?? ""} required><option value="">Select a person</option>{action && !members.some((member) => member.id === action.owner_user_id) && <option value={action.owner_user_id}>Current owner</option>}{members.map((member) => <option key={member.id} value={member.id}>{member.display_name}</option>)}</select></label><label>Due date<input name="due_date" type="date" defaultValue={action?.due_date ?? ""} required /></label></div><div className="ncr-form-actions"><button className="primary-action compact-action" type="submit">{action ? "Save action" : "Add action"}</button></div></fieldset></form>}
      {canManage && record.state === "action_planned" && visibleActions.length > 0 && <div className="ncr-form-actions"><button className="primary-action compact-action" type="button" disabled={busy} onClick={() => void command(record, "implementation/start", "POST", { expected_version: record.row_version }, "Implementation started. Planned action details are locked.")}>Start implementation</button></div>}
      {canManage && record.state === "implementation" && <div className="ncr-form-actions"><button className="primary-action compact-action" type="button" disabled={busy} onClick={() => void command(record, "effectiveness-review/start", "POST", { expected_version: record.row_version }, "All active actions are ready for effectiveness review.")}>Submit for effectiveness review</button></div>}
    </section>;
  }

  function editor(record?: CAPA) {
    return <form className="ncr-editor" key={record?.id ?? "new"} onSubmit={(event) => void save(event, record)}>
      <h3>{record ? `Edit ${record.code}` : "Register a corrective action"}</h3>
      <fieldset className="ncr-editor-content" disabled={busy}>
        {!record && <div className="ncr-reference-search">
          <div><label>Find a process<input value={processSearch} maxLength={160} onChange={(event) => { setProcessSearch(event.target.value); setProcessOffset(0); }} /></label><nav aria-label="Process pages"><button type="button" disabled={processOffset === 0} onClick={() => setProcessOffset(Math.max(0, processOffset - pageSize))}>Previous</button><button type="button" disabled={processes.length < pageSize} onClick={() => setProcessOffset(processOffset + pageSize)}>More</button></nav></div>
          {sourceType !== "other" && <div><label>Find {sourceType === "ncr" ? "a nonconformity" : "a risk"}<input value={originSearch} maxLength={160} onChange={(event) => { setOriginSearch(event.target.value); setOriginOffset(0); }} disabled={!canReadOrigin} /></label><nav aria-label="Source pages"><button type="button" disabled={originOffset === 0} onClick={() => setOriginOffset(Math.max(0, originOffset - pageSize))}>Previous</button><button type="button" disabled={origins.length < pageSize} onClick={() => setOriginOffset(originOffset + pageSize)}>More</button></nav></div>}
        </div>}
        <div className="ncr-form-grid">
          {!record && <><label>Code<input name="code" required maxLength={40} /></label><label>Process<select value={processId} required onChange={(event) => setProcessId(event.target.value)}><option value="">Select an active process</option>{processId && !processes.some((item) => item.id === processId) && <option value={processId}>Selected process</option>}{processes.filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>
            <label>Source<select value={sourceType} onChange={(event) => { setSourceType(event.target.value as CAPA["source_type"]); setOriginId(""); setOrigins([]); setOriginSearch(""); setOriginOffset(0); }}><option value="other">Other</option><option value="ncr">Nonconformity</option><option value="risk">Risk</option></select></label>
            {sourceType !== "other" && <label>Source record<select value={originId} required disabled={!canReadOrigin} onChange={(event) => setOriginId(event.target.value)}><option value="">Select a source</option>{originId && !origins.some((item) => item.id === originId) && <option value={originId}>Selected source</option>}{origins.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>}</>}
          <label className="ncr-wide">Title<input name="name" defaultValue={record?.name ?? ""} required maxLength={160} /></label>
          {(!record || record.state === "draft") && <label className="ncr-wide">Source reference (optional)<input name="source_reference" defaultValue={record?.source_reference ?? ""} maxLength={160} placeholder="External report or case number" /></label>}
          <label className="ncr-wide">Problem statement<textarea name="problem_statement" defaultValue={record?.problem_statement ?? ""} required maxLength={4000} rows={4} /></label>
          <label>Target date<input type="date" name="target_date" defaultValue={record?.target_date ?? ""} /></label>
          {record?.state === "analysis" ? <p>Root cause method: {label(record.root_cause_method ?? "")}</p> : <label>Root cause method<select name="root_cause_method" defaultValue={record?.root_cause_method ?? ""}><option value="">Choose later</option><option value="5why">5 Why</option><option value="fishbone">Fishbone</option><option value="is_is_not">Is / Is Not</option><option value="other">Other</option></select></label>}
        </div>
        <div className="ncr-reference-search"><div><label>Find a responsible person<input value={memberSearch} maxLength={160} onChange={(event) => { setMemberSearch(event.target.value); setMemberOffset(0); }} /></label><nav aria-label="Member pages"><button type="button" disabled={memberOffset === 0} onClick={() => setMemberOffset(Math.max(0, memberOffset - pageSize))}>Previous</button><button type="button" disabled={members.length < pageSize} onClick={() => setMemberOffset(memberOffset + pageSize)}>More</button></nav></div></div>
        <div className="ncr-form-grid"><label>Responsible person<select value={ownerId} onChange={(event) => setOwnerId(event.target.value)}><option value="">Unassigned</option>{ownerId && !members.some((item) => item.id === ownerId) && <option value={ownerId}>Selected member</option>}{members.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label></div>
        <div className="ncr-form-actions"><button className="primary-action compact-action" type="submit" disabled={!record && (!processId || !canReadOrigin || (sourceType !== "other" && !originId))}>{record ? "Save details" : "Register draft"}</button><button className="secondary-action compact-action" type="button" onClick={() => { setCreating(false); setEditing(false); }}>Cancel</button></div>
      </fieldset>
    </form>;
  }

  return <section className="ncr-panel" aria-labelledby="capa-heading" aria-busy={loading || busy}>
    <div className="workspace-heading"><div><p className="eyebrow">Continuous improvement</p><h2 id="capa-heading"><ClipboardCheck size={22} aria-hidden="true" /> Corrective actions</h2><p className="workspace-subtitle">Register a CAPA with a traceable nonconformity or risk source.</p></div><button className="secondary-action compact-action" type="button" disabled={busy || !unitId} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} aria-hidden="true" /> Refresh</button></div>
    <fieldset className="ncr-toolbar" disabled={busy}><label>Organization scope<select value={unitId} onChange={(event) => { setUnitId(event.target.value); onUnitChange?.(event.target.value); setCaps([]); setRows([]); setSelectedId(""); setCreating(false); setEditing(false); setSearch(""); setQuery({ q: "", offset: 0 }); }}><option value="">Select a unit</option>{units.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></label>{canRead && <form onSubmit={(event) => { event.preventDefault(); setCreating(false); setEditing(false); setQuery({ q: search.trim(), offset: 0 }); }}><label>Find by code or title<input value={search} maxLength={160} onChange={(event) => setSearch(event.target.value)} /></label><button className="secondary-action compact-action" type="submit">Search</button></form>}</fieldset>
    {error && <p className="denied-state" role="alert">{error}</p>}{notice && <p className="workflow-message" role="status">{notice}</p>}
    {loading ? <RecordWorkspaceSkeleton label="Loading corrective action access and records" /> : !unitId ? <p className="ncr-empty">Select an active organization unit.</p> : !canRead ? <p className="ncr-empty">No corrective action read responsibility is assigned for this unit.</p> : <>
      {canManage && <div className="ncr-create-action"><button className="primary-action compact-action" type="button" disabled={busy || !canCreate} onClick={() => { setCreating((value) => !value); setEditing(false); setSourceType("other"); setProcessId(""); setOriginId(""); setOwnerId(""); }}><Plus size={16} aria-hidden="true" /> New corrective action</button>{!canCreate && <p className="qms-history-caption">Process read responsibility is needed to register a CAPA.</p>}</div>}
      {creating && canCreate && editor()}
      <div className="ncr-register-grid"><aside aria-label="Corrective action register"><h3>Register <span>{rows.length}</span></h3>{rows.length ? <ul className="ncr-record-list">{rows.map((row) => <li key={row.id}><button type="button" aria-pressed={row.id === selectedId} disabled={busy} onClick={() => { setSelectedId(row.id); setCreating(false); setEditing(false); }}><span className="ncr-list-heading"><strong>{row.code}</strong><span className="process-status">{label(row.state)}</span></span><span>{row.name}</span><small>{label(row.source_type)}{(row.source_code || row.source_reference) ? ` · ${row.source_code || row.source_reference}` : ""}</small></button></li>)}</ul> : <p className="ncr-empty">No corrective actions match this scope and search.</p>}<nav className="ncr-pagination" aria-label="Corrective action pages"><button type="button" disabled={busy || query.offset === 0} onClick={() => setQuery({ ...query, offset: Math.max(0, query.offset - pageSize) })}>Previous</button><span>Page {Math.floor(query.offset / pageSize) + 1}</span><button type="button" disabled={busy || rows.length < pageSize} onClick={() => setQuery({ ...query, offset: query.offset + pageSize })}>Next</button></nav></aside>
        <div>{selected ? <article className="ncr-detail"><div className="ncr-detail-heading"><div><p className="eyebrow">{selected.code} · {label(selected.source_type)}</p><h3>{selected.name}</h3></div><span className="process-status">{label(selected.state)}</span></div><p className="ncr-description">{selected.problem_statement}</p><dl className="ncr-metadata"><div><dt>Source</dt><dd>{selected.source_code || "Other source"}</dd></div>{selected.source_reference && <div><dt>Source reference</dt><dd>{selected.source_reference}</dd></div>}<div><dt>Source state at registration</dt><dd>{selected.source_state ? label(selected.source_state) : "Not applicable"}</dd></div><div><dt>Target</dt><dd>{selected.target_date ?? "Not set"}</dd></div><div><dt>Root cause method</dt><dd>{selected.root_cause_method ? label(selected.root_cause_method) : "Not selected"}</dd></div></dl><p className="qms-history-caption">{selected.state === "draft" ? "Choose a root cause method and start analysis." : selected.state === "analysis" ? "Document the investigation, then start the action plan." : selected.state === "action_planned" ? "The verified investigation is locked. Assign actions with owners and due dates before execution." : selected.state === "implementation" ? "Execute actions and record an independent verification." : selected.state === "effectiveness_review" ? "Actions are locked while effectiveness is assessed." : selected.state === "effective" ? "Effectiveness was confirmed. Add closure notes to finish." : selected.state === "cancelled" ? "This corrective action was cancelled with a recorded reason." : "This corrective action is closed and its history is preserved."}</p>{canManage && ["draft", "analysis"].includes(selected.state) && <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => { setEditing((value) => !value); setCreating(false); setOwnerId(selected.owner_user_id ?? ""); }}>{editing ? "Cancel editing" : "Edit details"}</button>}{editing && canManage && editor(selected)}{canManage && !editing && selected.state === "draft" && <button className="primary-action compact-action" type="button" disabled={busy || !selected.root_cause_method} onClick={() => void command(selected, "analysis/start", "POST", { expected_version: selected.row_version }, "Root cause analysis started with a fixed method template.")}>Start analysis</button>}{selected.state === "analysis" && !editing && <>{analysisEditor(selected)}{canManage && planEditor(selected)}</>}{["action_planned", "implementation", "effectiveness_review", "effective", "closed", "cancelled"].includes(selected.state) && <><div className="ncr-editor"><h4>Verified investigation</h4><p>{selected.analysis_summary}</p><h4>Root cause</h4><p>{selected.verified_root_cause}</p><h4>Action plan scope</h4><p>{selected.plan_summary}</p><p className="qms-history-caption">Planned {selected.planned_at ? new Date(selected.planned_at).toLocaleString() : ""}</p></div>{actionPanel(selected)}{(["effectiveness_review", "effective", "closed"].includes(selected.state) || reviews.some((item) => item.capa_id === selected.id)) && reviewPanel(selected)}</>}<CAPASourceTraceability key={`source-${selected.id}-${selected.row_version}`} source={selected} />{caps.includes("control_instances.read") && <CAPATraceLinks key={`trace-${selected.id}-${unitId}`} capa={selected} canRead={canRead && caps.includes("control_instances.read")} canManage={canManage} disabled={busy} onChanged={refreshLinksParent} onAccessChanged={linksAccessChanged} />}{caps.includes("documents.read") && <CAPADocumentLinks key={`${selected.id}-${unitId}`} capa={selected} canRead={canRead && caps.includes("documents.read")} canManage={canManage} disabled={busy} onChanged={refreshLinksParent} onAccessChanged={linksAccessChanged} />}{cancelPanel(selected)}</article> : <div className="ncr-empty"><strong>Select a record</strong><p>Review its source and problem statement.</p></div>}</div></div>
    </>}
  </section>;
}
