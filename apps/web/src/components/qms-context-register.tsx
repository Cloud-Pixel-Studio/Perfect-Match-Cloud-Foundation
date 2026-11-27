"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { PartySourceLinks } from "./party-source-links";
import {
  ContextError, contextCategories, contextHistory, contextPageSize, contextRelevance,
  contextStates, getContextPermissions, listContext, listResponsiblePeople, partyTypes, saveContext,
  partyRequirementLimit, partySources, requirementDispositions, requirementReviewBlocker, trimRequirementText,
  type ContextCommand, type ContextFields, type ContextKind, type ContextPermission,
  type ContextRecord, type ContextRevision, type ContextScope, type ContextState, type ResponsiblePerson,
  type PartyRequirement, type PartySource,
} from "../lib/qms-context";

const captions = { issues: "Context issues", "interested-parties": "Interested parties" };
const relevanceLabels = { under_review: "Undecided", relevant: "Relevant", not_relevant: "Not relevant" };
const stateLabels = { draft: "Pending review", active: "Reviewed", retired: "Retired" };
const requirementLabels = {
  pending: "Decision pending",
  addressed_by_qms: "Address in the QMS",
  outside_qms: "Keep outside the QMS",
};
const partySourcePermission = {
  process: "processRead", document: "documentRead", evidence: "evidenceRead", risk: "riskRead",
} as const;
const textLabel = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);
const today = () => new Date().toISOString().slice(0, 10);
type Editor = { action: "create" } | { action: "edit" | "review" | "retire"; entry: ContextRecord };

function KindForm({ kind, editor, scope, busy, onSave, onCancel }: {
  kind: ContextKind; editor: Editor; scope: ContextScope; busy: boolean;
  onSave: (command: ContextCommand) => void; onCancel: () => void;
}) {
  const entry = "entry" in editor ? editor.entry : null;
  const [people, setPeople] = useState<ResponsiblePerson[]>([]);
  const [peopleOffset, setPeopleOffset] = useState(0);
  const [peopleState, setPeopleState] = useState<"loading" | "more" | "ready" | "error">("loading");
  const [requirements, setRequirements] = useState(entry?.party_requirements ?? []);
  const [absenceReason, setAbsenceReason] = useState(entry?.no_requirements_reason ?? "");
  const editContent = editor.action === "create" || editor.action === "edit";
  const issues = kind === "issues";
  useEffect(() => {
    if (!editContent) return;
    const controller = new AbortController();
    void listResponsiblePeople(scope, peopleOffset, controller.signal).then(page => {
      if (controller.signal.aborted) return;
      setPeople(previous => peopleOffset === 0 ? page : previous.concat(page));
      setPeopleState(page.length === 100 ? "more" : "ready");
    }).catch(() => {
      if (!controller.signal.aborted) setPeopleState("error");
    });
    return () => controller.abort();
  }, [scope, peopleOffset, editContent]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const value = (field: string) => String(data.get(field) ?? "").trim();
    if (editor.action === "review") {
      onSave({ action: "review", entry: editor.entry, note: value("note"), review_due_on: value("review_due_on") });
    } else if (editor.action === "retire") {
      onSave({ action: "retire", entry: editor.entry, note: value("note") });
    } else {
      const fields: ContextFields = {
        code: value("code"), name: value("name"), classification: value("classification"),
        category: issues ? value("category") : "",
        relevance: value("relevance") as ContextFields["relevance"], description: value("description"),
        requirements: value("requirements"), evidence_summary: value("evidence_summary"),
        owner_user_id: value("owner_user_id"), review_due_on: value("review_due_on"),
      };
      if (!issues) {
        fields.party_requirements = requirements.map(requirement => ({
          ...requirement,
          statement: trimRequirementText(requirement.statement),
          source: trimRequirementText(requirement.source),
          rationale: trimRequirementText(requirement.rationale),
        }));
        fields.no_requirements_reason = requirements.length === 0 ? trimRequirementText(absenceReason) : "";
      }
      if (!fields.code || !fields.name || !fields.description) {
        const field = event.currentTarget.elements.namedItem(!fields.code ? "code" : !fields.name ? "name" : "description");
        if (field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement) {
          field.value = "";
          field.reportValidity();
        }
        return;
      }
      if (editor.action === "edit") onSave({ action: "edit", entry: editor.entry, fields });
      else onSave({ action: "create", fields });
    }
  }

  return <form className="project-summary" onSubmit={submit}>
    <fieldset disabled={busy} className="context-fields">
      <legend>{editor.action === "create" ? issues ? "New context issue" : "New interested party" : `${textLabel(editor.action)} ${entry?.code}`}</legend>
      {editContent ? <>
        <div className="project-fields">
          <label>Code<input name="code" required maxLength={40} defaultValue={entry?.code} /></label>
          <label>Name<input name="name" required maxLength={160} defaultValue={entry?.name} /></label>
          <label>{issues ? "Source" : "Party type"}
            <select name="classification" defaultValue={entry?.classification}>
              {(issues ? ["internal", "external"] : partyTypes).map(type => <option key={type} value={type}>{textLabel(type)}</option>)}
            </select>
          </label>
          {issues && <label>Category<select name="category" defaultValue={entry?.category ?? "other"}>
            {contextCategories.map(category => <option key={category} value={category}>{textLabel(category)}</option>)}
          </select></label>}
          <label>{issues ? "Climate change relevance for this issue" : "Relevance to the QMS"}
            <select name="relevance" defaultValue={entry?.relevance ?? "under_review"}>
              {contextRelevance.map(relevance => <option key={relevance} value={relevance}>{relevanceLabels[relevance]}</option>)}
            </select>
          </label>
          <label>Responsible person
            <select name="owner_user_id" required defaultValue={entry?.owner_user_id ?? scope.userId}>
              <option value="">Select a person</option>
              <option value={scope.userId}>Myself</option>
              {entry && entry.owner_user_id !== scope.userId && <option value={entry.owner_user_id}>
                {people.find(person => person.user_id === entry.owner_user_id)?.display_name ?? "Current responsible person"}
              </option>}
              {people.filter(person => person.user_id !== scope.userId && person.user_id !== entry?.owner_user_id)
                .map(person => <option key={person.user_id} value={person.user_id}>{person.display_name}</option>)}
            </select>
          </label>
          <label>Review due<input name="review_due_on" type="date" required defaultValue={entry?.review_due_on} /></label>
        </div>
        {peopleState === "more" && <button type="button" className="secondary-action compact-action" onClick={() => {
          setPeopleState("loading"); setPeopleOffset(offset => offset + 100);
        }}>Load more people</button>}
        {peopleState === "loading" && <p role="status" className="project-help">Loading responsible people…</p>}
        {peopleState === "error" && <p role="status" className="project-help">The company directory could not be loaded. Reopen the form to retry.</p>}
        <label>{issues ? "Issue and rationale for climate relevance" : "Needs and expectations"}
          <textarea name="description" rows={3} required maxLength={4000} defaultValue={entry?.description} />
        </label>
        {!issues && <PartyRequirementsFields requirements={requirements} onChange={setRequirements}
          absenceReason={absenceReason} onAbsenceChange={setAbsenceReason} />}
        <label>{issues ? "Impact on the quality system" : "Additional requirements notes"}
          <textarea name="requirements" rows={3} maxLength={4000} defaultValue={entry?.requirements} />
        </label>
        <label>Supporting evidence summary<textarea name="evidence_summary" rows={2} maxLength={4000} defaultValue={entry?.evidence_summary} /></label>
        {entry?.status === "active" && <p className="project-help">Saving these changes sends this record back for independent review.</p>}
      </> : <>
        <label>{editor.action === "review" ? "Review decision and rationale" : "Reason for retirement"}
          <textarea name="note" required maxLength={1000} rows={3} />
        </label>
        {editor.action === "review" && <label>Next review date
          <input name="review_due_on" required type="date" defaultValue={entry && entry.review_due_on > today() ? entry.review_due_on : undefined} />
        </label>}
        {editor.action === "retire" && <p className="project-help">Retired records remain visible in the register and history.</p>}
      </>}
    </fieldset>
    <div className="project-actions">
      <button type="submit" className="primary-action compact-action" disabled={busy}>
        {busy ? "Saving…" : editor.action === "review" ? "Record review" : editor.action === "retire" ? "Retire record" : "Save draft"}
      </button>
      <button type="button" className="secondary-action compact-action" disabled={busy} onClick={onCancel}>Cancel</button>
    </div>
  </form>;
}

function PartyRequirementsFields({ requirements, onChange, absenceReason, onAbsenceChange }: {
  requirements: PartyRequirement[];
  onChange: (next: PartyRequirement[]) => void;
  absenceReason: string;
  onAbsenceChange: (next: string) => void;
}) {
  function change(id: string, changes: Partial<PartyRequirement>) {
    onChange(requirements.map(item => item.id === id ? { ...item, ...changes } : item));
  }

  return <section className="party-requirements" aria-label="Individual requirements">
    <h4>Individual requirements</h4>
    <p className="project-help">Record each requirement and decide whether the QMS will address it.</p>
    {requirements.map((item, index) => <fieldset key={item.id} className="context-fields project-reference-kind">
      <legend>Requirement {index + 1}</legend>
      <label>Requirement
        <textarea value={item.statement} onChange={event => change(item.id, { statement: event.target.value })}
          required rows={2} maxLength={360} />
      </label>
      <div className="project-fields">
        <label>Source<input value={item.source} onChange={event => change(item.id, { source: event.target.value })}
          required maxLength={200} /></label>
        <label>QMS decision
          <select value={item.disposition} onChange={event => change(item.id, {
            disposition: event.target.value as PartyRequirement["disposition"],
          })}>
            {requirementDispositions.map(disposition => <option key={disposition} value={disposition}>
              {requirementLabels[disposition]}
            </option>)}
          </select>
        </label>
      </div>
      <label>Decision rationale
        <textarea value={item.rationale} onChange={event => change(item.id, { rationale: event.target.value })}
          required={item.disposition !== "pending"} rows={2} maxLength={600} />
      </label>
      <div className="project-actions">
        <button className="secondary-action compact-action" type="button" onClick={() => {
          onChange(requirements.filter(requirement => requirement.id !== item.id));
        }}>Remove requirement {index + 1}</button>
      </div>
    </fieldset>)}
    {requirements.length === 0 && <label>Reason no relevant requirements were identified
      <textarea rows={2} maxLength={600} value={absenceReason} onChange={event => onAbsenceChange(event.target.value)} />
    </label>}
    <div className="project-actions">
      <button className="secondary-action compact-action" type="button" disabled={requirements.length >= partyRequirementLimit}
        onClick={() => onChange(requirements.concat({
          id: crypto.randomUUID(), statement: "", source: "", disposition: "pending", rationale: "",
        }))}>Add requirement</button>
    </div>
    {requirements.length >= partyRequirementLimit && <p role="status" className="project-help">This party has reached the 20-requirement limit.</p>}
  </section>;
}

function RecordSummary({ record }: { record: ContextRecord }) {
  const blocker = requirementReviewBlocker(record);
  const requirements = record.party_requirements ?? [];
  return <>
    <p className="project-help">
      {stateLabels[record.status]} · {textLabel(record.classification)} · {relevanceLabels[record.relevance]} · Review due{" "}
      <time dateTime={record.review_due_on}>{record.review_due_on}</time>
      {record.status === "active" && record.review_due_on < today() && " (overdue)"}
    </p>
    {record.owner_display_name && <p className="project-help">Responsible person · {record.owner_display_name}</p>}
    <p className="project-notes">{record.description}</p>
    {record.requirements && <p className="project-notes"><strong>{record.kind === "issues" ? "QMS impact" : "Requirements and response"}</strong><br />{record.requirements}</p>}
    {record.kind === "interested-parties" && <>
      {blocker && record.status !== "retired" && <p className="project-help">{blocker}</p>}
      {record.no_requirements_reason && <p className="project-notes">
        <strong>No relevant requirements identified</strong><br />{record.no_requirements_reason}
      </p>}
      {requirements.length > 0 && <details className="party-requirements">
        <summary>Requirements ({requirements.length})</summary>
        <ul className="project-reference-list">
          {requirements.map(item => <li key={item.id} className="project-reference-kind">
            <strong>{item.statement}</strong>
            <p className="project-help">{requirementLabels[item.disposition]} · {item.source}</p>
            {item.rationale && <p className="project-notes">{item.rationale}</p>}
          </li>)}
        </ul>
      </details>}
    </>}
    {record.evidence_summary && <p className="project-notes"><strong>Supporting evidence</strong><br />{record.evidence_summary}</p>}
    {record.decision_note && <p className="project-notes"><strong>{record.status === "retired" ? "Retirement reason" : "Review decision"}</strong><br />{record.decision_note}</p>}
  </>;
}

function History({ scope, record, onError }: {
  scope: ContextScope; record: ContextRecord; onError: (cause: unknown) => void;
}) {
  const [revisions, setRevisions] = useState<ContextRevision[] | null>(null);
  const [before, setBefore] = useState(2147483647);
  const [more, setMore] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void contextHistory(scope, record, before, controller.signal).then(page => {
      if (controller.signal.aborted) return;
      setRevisions(previous => (previous ?? []).concat(page));
      setMore(page.length === contextPageSize);
    }).catch(cause => { if (!controller.signal.aborted) onError(cause); });
    return () => controller.abort();
  }, [scope, record, before, onError]);
  return <section aria-label="Record history">
    <h5>Record history</h5>
    {revisions === null ? <p role="status">Loading versions…</p> : <ol className="project-reference-list">
      {revisions.map(({ command, snapshot }) => <li key={snapshot.row_version}>
        <details>
          <summary>Version {snapshot.row_version} · {textLabel(command)} · <time dateTime={snapshot.updated_at}>{new Date(snapshot.updated_at).toLocaleString()}</time></summary>
          <p><strong>{snapshot.code} · {snapshot.name}</strong></p>
          <RecordSummary record={snapshot} />
          <p className="project-help">Changed by {snapshot.updated_by_user_id}</p>
        </details>
      </li>)}
    </ol>}
    {more && revisions?.length ? <button className="secondary-action compact-action" type="button" onClick={() => {
      setMore(false); setBefore(revisions[revisions.length - 1].snapshot.row_version);
    }}>Load earlier versions</button> : null}
  </section>;
}

export function QMSContextRegister({ scope, onEditingChange, locked }: {
  scope: ContextScope; onEditingChange: (editing: boolean) => void; locked: boolean;
}) {
  const [opened, setOpened] = useState(false);
  const [kind, setKind] = useState<ContextKind>("issues");
  const [status, setStatus] = useState<ContextState | "">("");
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [permission, setPermission] = useState<ContextPermission | null>(null);
  const [page, setPage] = useState<Awaited<ReturnType<typeof listContext>> | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [historyId, setHistoryId] = useState("");
  const [openLinks, setOpenLinks] = useState<{ partyId: string; source: PartySource } | null>(null);
  const [linkBusy, setLinkBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [stale, setStale] = useState(false);
  const commandRequest = useRef<AbortController | null>(null);

  useEffect(() => () => commandRequest.current?.abort(), []);
  useEffect(() => {
    onEditingChange(Boolean(editor) || linkBusy);
    return () => onEditingChange(false);
  }, [editor, linkBusy, onEditingChange]);

  const reportFailure = useCallback((cause: unknown) => {
    if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
      setPage(null); setEditor(null); setPermission(null); setHistoryId(""); setOpenLinks(null);
      setError("Your access or company changed. Refresh the register to verify access.");
    } else {
      setError("The register could not be loaded. Refresh to retry.");
      setHistoryId("");
    }
  }, []);

  useEffect(() => {
    if (!opened) return;
    const controller = new AbortController();
    void (async () => {
      const permissions = await getContextPermissions(scope, controller.signal);
      const result = permissions.read ? await listContext(scope, kind, status, offset, controller.signal) : null;
      if (controller.signal.aborted) return;
      setPermission(permissions);
      setPage(result);
    })().catch(cause => { if (!controller.signal.aborted) reportFailure(cause); });
    return () => controller.abort();
  }, [opened, scope, kind, status, offset, reload, reportFailure]);

  function resetRead() {
    setPage(null); setPermission(null); setHistoryId(""); setError(""); setNotice(""); setStale(false);
    setEditor(null);
    setOpenLinks(null);
  }

  async function mutate(command: ContextCommand) {
    if (commandRequest.current || stale || linkBusy) return;
    const controller = new AbortController();
    commandRequest.current = controller;
    setBusy(true); setError(""); setNotice("");
    try {
      const csrf = document.cookie.split("; ").find(cookie => cookie.startsWith("pm_csrf="))?.slice(8) ?? "";
      const result = await saveContext(scope, kind, command, decodeURIComponent(csrf), controller.signal);
      if (controller.signal.aborted) return;
      resetRead();
      setStatus(""); setOffset(0); setReload(current => current + 1);
      setNotice(`${result.code} · ${stateLabels[result.status]} · Version ${result.row_version}`);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        reportFailure(cause);
      } else if (cause instanceof ContextError && cause.status === 422) {
        setError("Check the required fields and their values before saving.");
      } else {
        setStale(true);
        setError(cause instanceof ContextError && cause.status === 409
          ? "The version, code, responsible person or review date conflicts. Refresh and check the record before trying again."
          : "The result could not be verified. Refresh the register before trying again.");
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
      commandRequest.current = null;
    }
  }

  return <section className="qms-project-planner context-register" aria-labelledby="context-register-heading">
    <header className="project-panel-heading">
      <h3 id="context-register-heading">Context and interested parties</h3>
      <button type="button" className="secondary-action compact-action" aria-expanded={opened} disabled={busy || linkBusy || Boolean(editor)} onClick={() => {
        resetRead(); setOpened(!opened);
      }}>{opened ? "Close register" : "View context register"}</button>
    </header>
    {opened && <>
      <div className="project-toolbar">
        <label>Register<select value={kind} disabled={Boolean(editor) || linkBusy} onChange={event => {
          resetRead(); setOffset(0); setKind(event.target.value as ContextKind);
        }}>{Object.entries(captions).map(([value, caption]) => <option key={value} value={value}>{caption}</option>)}</select></label>
        {permission?.read && <label>Status<select value={status} disabled={Boolean(editor) || linkBusy} onChange={event => {
          resetRead(); setOffset(0); setStatus(event.target.value as ContextState | "");
        }}><option value="">All statuses</option>{contextStates.map(state => <option value={state} key={state}>{stateLabels[state]}</option>)}</select></label>}
        <button type="button" className="secondary-action compact-action" disabled={busy || linkBusy || Boolean(editor && !stale)} onClick={() => {
          resetRead(); setReload(current => current + 1);
        }}>Refresh register</button>
        {permission?.manage && !editor && <button type="button" className="primary-action compact-action" disabled={locked || linkBusy} onClick={() => {
          setNotice(""); setError(""); setEditor({ action: "create" });
        }}>{kind === "issues" ? "New issue" : "New interested party"}</button>}
      </div>
      {error && <p role="alert" className="project-feedback">{error}</p>}
      {notice && <p role="status" className="project-feedback">{notice}</p>}
      {!permission && !error && <p role="status" className="project-skeleton">Checking register access…<span aria-hidden="true" /></p>}
      {permission && !permission.read && <p role="status">Access to this register requires the context read permission for the selected unit.</p>}
      {editor && <KindForm kind={kind} editor={editor} scope={scope} busy={busy} onSave={command => {
        void mutate(command);
      }} onCancel={() => { setEditor(null); setError(""); setStale(false); }} />}
      {page?.records.length === 0 && <p role="status">No records match this view.</p>}
      {page && <ul className="project-reference-list">
        {page.records.map(record => <li key={record.id} className="project-reference-card">
          <h4>{record.code} · {record.name}</h4>
          <RecordSummary record={record} />
          <div className="project-actions">
            <button type="button" className="secondary-action compact-action" aria-expanded={historyId === record.id} onClick={() => setHistoryId(current => current === record.id ? "" : record.id)}>
              {historyId === record.id ? "Close history" : "Version history"}
            </button>
            {record.kind === "interested-parties" && partySources.map(source => {
              if (!permission?.[partySourcePermission[source]]) return null;
              const expanded = openLinks?.partyId === record.id && openLinks.source === source;
              return <button key={source} type="button" className="secondary-action compact-action" disabled={linkBusy}
                aria-expanded={expanded} onClick={() => setOpenLinks(expanded ? null : { partyId: record.id, source })}>
                {expanded ? "Hide" : "View"} {source} links
              </button>;
            })}
            {permission?.manage && record.status !== "retired" && <>
              <button type="button" className="secondary-action compact-action" disabled={Boolean(editor) || locked || linkBusy} onClick={() => setEditor({ action: "edit", entry: record })}>Edit {record.code}</button>
              <button type="button" className="secondary-action compact-action" disabled={Boolean(editor) || locked || linkBusy} onClick={() => setEditor({ action: "retire", entry: record })}>Retire {record.code}</button>
            </>}
            {permission?.review && record.status !== "retired" && record.relevance !== "under_review" && !requirementReviewBlocker(record)
              && record.created_by_user_id !== scope.userId && record.content_editor_user_id !== scope.userId &&
              <button type="button" className="secondary-action compact-action" disabled={Boolean(editor) || locked || linkBusy} onClick={() => setEditor({ action: "review", entry: record })}>Review {record.code}</button>}
          </div>
          {historyId === record.id && <History scope={scope} record={record} onError={reportFailure} />}
          {openLinks?.partyId === record.id && permission?.[partySourcePermission[openLinks.source]] && <PartySourceLinks
            key={`${record.row_version}:${openLinks.source}`} source={openLinks.source}
            scope={scope} record={record} canManage={permission.manage} locked={Boolean(editor) || locked}
            onBusy={setLinkBusy} onAccessFailure={reportFailure} onChanged={action => {
              const source = openLinks.source === "risk" ? "Risk or opportunity" : textLabel(openLinks.source);
              resetRead();
              setOpenLinks(openLinks);
              setStatus(""); setOffset(0); setReload(current => current + 1);
              setNotice(action === "link" ? `${source} linked and party version updated.` : `${source} link withdrawn. The history was preserved.`);
            }} />}
        </li>)}
      </ul>}
      {(offset > 0 || page?.hasMore) && <nav className="project-actions" aria-label="Context register pages">
        <button type="button" className="secondary-action compact-action" disabled={offset === 0 || Boolean(editor) || linkBusy} onClick={() => {
          resetRead(); setOffset(current => current - contextPageSize);
        }}>Previous page</button>
        <span className="project-help">Page {offset / contextPageSize + 1}</span>
        <button type="button" className="secondary-action compact-action" disabled={!page?.hasMore || Boolean(editor) || linkBusy} onClick={() => {
          resetRead(); setOffset(current => current + contextPageSize);
        }}>Next page</button>
      </nav>}
    </>}
  </section>;
}
