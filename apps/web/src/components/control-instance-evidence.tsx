"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Evidence = {
  id: string; control_instance_id: string; requirement_definition_id: string; sequence: number;
  name: string; description: string; acceptance_criteria: string; evidence_type: string;
  mandatory: boolean; document_id: string | null; document_revision_id: string | null;
  evidence_summary: string; status: string; submitted_by_user_id: string | null;
  submitted_at: string | null; reviewed_by_user_id: string | null; reviewed_at: string | null;
  review_decision: string; row_version: number;
};
type Document = { id: string; code: string; title: string; status: string };
type Revision = { id: string; document_id: string; revision: string; status: string; file_state: string };
type User = { id: string };

const api = "/api/identity";
const csrf = () => decodeURIComponent(document.cookie.split("; ").find((item) => item.startsWith("pm_csrf="))?.slice(8) ?? "");

export function ControlInstanceEvidence({
  instanceId, unitId, processId, canManage, canReview, canReadDocuments, targetEvidenceId,
}: { instanceId: string; unitId: string; processId: string; canManage: boolean; canReview: boolean; canReadDocuments: boolean; targetEvidenceId?: string }) {
  const [items, setItems] = useState<Evidence[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [revisions, setRevisions] = useState<Record<string, Revision[]>>({});
  const [currentUserId, setCurrentUserId] = useState("");
  const [summaries, setSummaries] = useState<Record<string, string>>({});
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [documentIds, setDocumentIds] = useState<Record<string, string>>({});
  const [revisionIds, setRevisionIds] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const targetFocused = useRef(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch(`${api}/control-instance-evidence?instance_id=${encodeURIComponent(instanceId)}`, { credentials: "include" });
      if (!response.ok) throw new Error("load");
      setItems(await response.json() as Evidence[]);
      const me = await fetch(`${api}/auth/me`, { credentials: "include" });
      if (me.ok) setCurrentUserId((await me.json() as User).id);
      if (canReadDocuments) {
        const docs = await fetch(`${api}/documents?unit_id=${encodeURIComponent(unitId)}&process_id=${encodeURIComponent(processId)}&limit=100`, { credentials: "include" });
        if (docs.ok) setDocuments((await docs.json() as Document[]).filter((row) => row.status === "active"));
      }
      setError("");
    } catch {
      setError("Required evidence could not be loaded. Refresh the workspace.");
    }
  }, [canReadDocuments, instanceId, processId, unitId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (!targetEvidenceId || targetFocused.current || !items.some((item) => item.id === targetEvidenceId)) return;
    targetFocused.current = true;
    const timer = window.setTimeout(() => document.getElementById(`control-evidence-${targetEvidenceId}`)?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [items, targetEvidenceId]);

  async function loadRevisions(documentId: string) {
    if (!documentId || revisions[documentId]) return;
    const response = await fetch(`${api}/documents/${documentId}/revisions`, { credentials: "include" });
    if (response.ok) {
      const rows = await response.json() as Revision[];
      setRevisions((current) => ({
        ...current,
        [documentId]: rows.filter((row) => row.status === "active" && row.file_state === "clean"),
      }));
    }
  }

  async function mutate(path: string, body: object, method: "PATCH" | "POST" = "POST") {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${api}${path}`, {
        method, credentials: "include", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(response.status === 403 ? "review" : response.status === 409 ? "conflict" : "save");
      await load();
    } catch (cause) {
      setError(cause instanceof Error && cause.message === "review"
        ? "A person other than the submitter must review this evidence."
        : cause instanceof Error && cause.message === "conflict"
          ? "Evidence changed or readiness is incomplete. Refresh and review its current state."
          : "Evidence could not be saved. Check the required fields and try again.");
    } finally { setBusy(false); }
  }

  const label: Record<string, string> = { draft: "Draft", submitted: "Submitted", accepted: "Accepted", rejected: "Changes requested" };

  return <details className="control-guidance-read control-instance-evidence" open={Boolean(targetEvidenceId)}>
    <summary>Required evidence <span className="qms-grant-status assigned">{items.filter((item) => item.mandatory).length} required</span></summary>
    {error && <p role="alert" className="denied-state">{error}</p>}
    {!items.length && <p>No evidence requirements were defined for this control.</p>}
    <ul className="control-instance-evidence-list">{items.map((item) => {
      const chosenDocument = documentIds[item.id] ?? item.document_id ?? "";
      const chosenRevision = revisionIds[item.id] ?? item.document_revision_id ?? "";
      const evidenceChanged = (summaries[item.id] !== undefined && summaries[item.id] !== item.evidence_summary)
        || (documentIds[item.id] !== undefined && documentIds[item.id] !== (item.document_id ?? ""))
        || (revisionIds[item.id] !== undefined && revisionIds[item.id] !== (item.document_revision_id ?? ""));
      const reviewAllowed = item.status === "submitted" && item.submitted_by_user_id !== currentUserId;
      return <li id={`control-evidence-${item.id}`} className={targetEvidenceId === item.id ? "action-target-record" : undefined} tabIndex={-1} key={item.id}>
        <div className="control-instance-activity-heading"><strong>{item.sequence}. {item.name}</strong>
          <span className={`qms-grant-status ${item.status === "accepted" ? "assigned" : "pending"}`}>{label[item.status] ?? item.status}</span>
        </div>
        {item.mandatory && <small>Acceptance required before implementation review</small>}
        {item.description && <p>{item.description}</p>}
        {item.acceptance_criteria && <p><strong>Acceptance criteria:</strong> {item.acceptance_criteria}</p>}
        {item.document_revision_id && <p><strong>Controlled document:</strong> {documents.find((doc) => doc.id === item.document_id)?.title ?? "Linked released revision"}</p>}
        {item.evidence_summary && <p><strong>Submitted evidence:</strong> {item.evidence_summary}</p>}
        {item.review_decision && <p><strong>Review decision:</strong> {item.review_decision}</p>}
        {canManage && ["draft", "rejected"].includes(item.status) && <div className="control-instance-evidence-editor">
          <label>Evidence summary<textarea rows={3} maxLength={4000} value={summaries[item.id] ?? item.evidence_summary}
            disabled={busy} onChange={(event) => setSummaries((current) => ({ ...current, [item.id]: event.target.value }))} /></label>
          {canReadDocuments && <>
            <label>Released controlled document<select disabled={busy} value={chosenDocument} onChange={(event) => {
              const id = event.target.value;
              setDocumentIds((current) => ({ ...current, [item.id]: id }));
              setRevisionIds((current) => ({ ...current, [item.id]: "" }));
              void loadRevisions(id);
            }}><option value="">No linked document</option>{documents.map((doc) => <option key={doc.id} value={doc.id}>{doc.code} · {doc.title}</option>)}</select></label>
            {chosenDocument && <label>Released revision<select disabled={busy} value={chosenRevision} onChange={(event) => setRevisionIds((current) => ({ ...current, [item.id]: event.target.value }))}>
              <option value="">Select released revision</option>{(revisions[chosenDocument] ?? []).map((revision) => <option key={revision.id} value={revision.id}>{revision.revision}</option>)}
            </select></label>}
          </>}
          <button className="secondary-action compact-action" type="button" disabled={busy || (chosenDocument !== "" && chosenRevision === "")}
            onClick={() => void mutate(`/control-instance-evidence/${item.id}`, {
              evidence_summary: summaries[item.id] ?? item.evidence_summary,
              ...(canReadDocuments ? { document_id: chosenDocument || null, document_revision_id: chosenRevision || null } : {}),
            }, "PATCH")}>Save evidence</button>
          <button className="secondary-action compact-action" type="button" disabled={busy || evidenceChanged || (!(summaries[item.id] ?? item.evidence_summary).trim() && !chosenRevision)}
            onClick={() => void mutate(`/control-instance-evidence/${item.id}/submit`, { expected_version: item.row_version })}>Submit for review</button>
        </div>}
        {reviewAllowed && canReview && <div className="control-instance-evidence-editor">
          <label>Reviewer decision<textarea rows={2} maxLength={1000} value={decisions[item.id] ?? ""}
            disabled={busy} onChange={(event) => setDecisions((current) => ({ ...current, [item.id]: event.target.value }))} /></label>
          <button className="secondary-action compact-action" type="button" disabled={busy || !(decisions[item.id] ?? "").trim()}
            onClick={() => void mutate(`/control-instance-evidence/${item.id}/review`, {
              expected_version: item.row_version, target_status: "accepted", decision: decisions[item.id],
            })}>Accept evidence</button>
          <button className="secondary-action compact-action" type="button" disabled={busy || !(decisions[item.id] ?? "").trim()}
            onClick={() => void mutate(`/control-instance-evidence/${item.id}/review`, {
              expected_version: item.row_version, target_status: "rejected", decision: decisions[item.id],
            })}>Request changes</button>
        </div>}
      </li>;
    })}</ul>
  </details>;
}
