"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  changePartySourceLink, ContextError, contextPageSize, partySourceCandidates, partySourceLinks,
  trimRequirementText, type ContextRecord, type ContextScope, type PartySource, type PartySourceCommand, type PartySourceLink,
} from "../lib/qms-context";

const processLabels = {
  current: "Current process version",
  changed: "Process has a newer version",
  archived: "Process archived",
  unavailable: "Current process unavailable",
};
const documentLabels = {
  current: "Current released revision",
  changed: "Document or revision updated",
  obsolete: "Document obsolete",
  superseded: "Revision superseded",
  unavailable: "Current revision unavailable",
};
const evidenceLabels = {
  current: "Accepted evidence",
  changed: "Evidence or implementation updated",
  implementation_archived: "Implementation archived",
  unavailable: "Current evidence unavailable",
};
const riskLabels = {
  assessed: "Assessed", action_required: "Action required", monitoring: "Monitoring",
  closed: "Closed", unavailable: "Current state unavailable",
};

function linkDetails(link: PartySourceLink) {
  if ("risk_id" in link) return {
    code: link.risk_code, name: link.risk_name, status: riskLabels[link.risk_state],
    version: `Linked risk register version ${link.risk_version}`,
  };
  if ("evidence_id" in link) return {
    code: link.control_code, name: link.evidence_name, status: evidenceLabels[link.evidence_state],
    version: `Linked evidence version ${link.evidence_version}`,
  };
  if ("document_id" in link) return {
    code: link.document_code, name: link.document_title, status: documentLabels[link.document_state],
    version: `Linked revision ${link.revision}`,
  };
  return {
    code: link.process_code, name: link.process_name, status: processLabels[link.process_state],
    version: `Linked process version ${link.process_version}`,
  };
}

export function PartySourceLinks({ source, scope, record, canManage, locked, onBusy, onChanged, onAccessFailure }: {
  source: PartySource;
  scope: ContextScope;
  record: ContextRecord;
  canManage: boolean;
  locked: boolean;
  onBusy: (busy: boolean) => void;
  onChanged: (kind: PartySourceCommand["kind"]) => void;
  onAccessFailure: (error: ContextError) => void;
}) {
  const [links, setLinks] = useState<Awaited<ReturnType<typeof partySourceLinks>> | null>(null);
  const [linkOffset, setLinkOffset] = useState(0);
  const [candidates, setCandidates] = useState<Awaited<ReturnType<typeof partySourceCandidates>> | null>(null);
  const [candidateOffset, setCandidateOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchRevision, setSearchRevision] = useState(0);
  const [selection, setSelection] = useState("");
  const [editing, setEditing] = useState<"add" | PartySourceLink | null>(null);
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState("");
  const command = useRef<AbortController | null>(null);
  const requirements = record.party_requirements?.filter(item => item.disposition === "addressed_by_qms") ?? [];
  const mayWrite = canManage && record.status !== "retired";
  const sourceLabel = { document: "Document", evidence: "Evidence", process: "Process", risk: "Risk" }[source];
  const sourcePlural = {
    document: "documents", evidence: "evidence records", process: "processes", risk: "risks and opportunities",
  }[source];
  const sourceArticle = { document: "a document", evidence: "evidence", process: "a process", risk: "a risk or opportunity" }[source];
  const selectPrompt = {
    document: "Select a released revision", evidence: "Select accepted evidence", process: "Select an active process",
    risk: "Select an assessed risk or opportunity",
  }[source];

  useEffect(() => () => {
    if (command.current) {
      command.current.abort();
      onBusy(false);
    }
  }, [onBusy]);

  useEffect(() => {
    const controller = new AbortController();
    void partySourceLinks(source, scope, record, linkOffset, controller.signal).then(page => {
      if (!controller.signal.aborted) setLinks(page);
    }).catch(cause => {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        onAccessFailure(cause);
        return;
      }
      setStale(true);
      setError(`Could not load ${source} links. Refresh the register to verify the party version.`);
    });
    return () => controller.abort();
  }, [source, scope, record, linkOffset, onAccessFailure]);

  useEffect(() => {
    if (editing !== "add" || !mayWrite) return;
    const controller = new AbortController();
    void partySourceCandidates(source, scope, record, search, candidateOffset, controller.signal).then(page => {
      if (!controller.signal.aborted) setCandidates(page);
    }).catch(cause => {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        onAccessFailure(cause);
        return;
      }
      setError(`Could not load eligible ${sourcePlural}. Retry the search or refresh the register.`);
    });
    return () => controller.abort();
  }, [source, sourcePlural, scope, record, editing, mayWrite, search, candidateOffset, searchRevision, onAccessFailure]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || command.current || !mayWrite || stale || locked) return;
    const fields = new FormData(event.currentTarget);
    const reason = trimRequirementText(String(fields.get("note") ?? ""));
    if (!reason) {
      setError("Enter a reason before saving.");
      return;
    }
    let change: PartySourceCommand;
    if (editing === "add") {
      const candidate = candidates?.items.find(item => item.id === selection);
      const requirementId = String(fields.get("requirement") ?? "");
      if (!candidate || !requirements.some(item => item.id === requirementId)) return;
      change = { kind: "link", requirementId, candidate, rationale: reason };
    } else {
      change = { kind: "remove", linkId: editing.id, reason };
    }
    const controller = new AbortController();
    command.current = controller;
    setBusy(true);
    onBusy(true);
    setError("");
    try {
      const token = document.cookie.split("; ").find(cookie => cookie.startsWith("pm_csrf="))?.slice(8) ?? "";
      await changePartySourceLink(source, scope, record, change, decodeURIComponent(token), controller.signal);
      if (!controller.signal.aborted) onChanged(change.kind);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        onAccessFailure(cause);
      } else if (cause instanceof ContextError && cause.status === 422) {
        setError(`Check the selected ${source}, requirement and rationale.`);
      } else {
        setStale(true);
        setError("The operation could not be confirmed. Refresh the register before retrying.");
      }
    } finally {
      command.current = null;
      if (!controller.signal.aborted) {
        setBusy(false);
        onBusy(false);
      }
    }
  }

  function showAdd() {
    setEditing("add");
    setSelection("");
    setCandidates(null);
    setError("");
  }

  function candidatePage(offset: number) {
    setCandidates(null);
    setSelection("");
    setCandidateOffset(offset);
  }

  return <section className={`project-summary party-${source}-links`} aria-label={`${sourceLabel} links`}>
    <h5>{sourceLabel} links</h5>
    {error && <p role="alert" className="project-feedback">{error}</p>}
    {!links && !error && <p role="status">Loading {source} links…</p>}
    {links?.items.length === 0 && <p role="status">No {sourcePlural} have been linked.</p>}
    {mayWrite && editing === null && requirements.length > 0 &&
      <button className="primary-action compact-action" type="button" disabled={busy || stale || locked} onClick={showAdd}>Link {sourceArticle}</button>}
    {mayWrite && requirements.length === 0 && <p className="project-help">Decide which requirements the QMS will address to link {sourceArticle}.</p>}
    {editing === "add" && <div className="project-toolbar">
      <label>Find {sourceArticle}
        <input type="search" maxLength={120} value={searchInput} disabled={busy}
          onChange={event => setSearchInput(event.target.value)} />
      </label>
      <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => {
        candidatePage(0); setSearch(searchInput.trim()); setError(""); setSearchRevision(value => value + 1);
      }}>Search {sourcePlural}</button>
    </div>}
    {editing !== null && <form className="project-summary" onSubmit={save}>
      <fieldset disabled={busy || locked} className="context-fields">
        <legend>{editing === "add" ? `New ${source} link` : `Withdraw link to ${linkDetails(editing).code}`}</legend>
        {editing === "add" && <>
          <label>Requirement
            <select name="requirement" required defaultValue={requirements.length === 1 ? requirements[0].id : ""}>
              <option value="" disabled>Select a requirement</option>
              {requirements.map(item => <option key={item.id} value={item.id}>{item.statement}</option>)}
            </select>
          </label>
          <label>{source === "risk" ? "Risk or opportunity" : sourceLabel}
            <select name="source" required value={selection} onChange={event => setSelection(event.target.value)}>
              <option value="" disabled>{candidates ? selectPrompt : `Loading ${sourcePlural}…`}</option>
              {candidates?.items.map(item => <option value={item.id} key={item.id}>
                {item.code} · {item.name}{"revision" in item ? ` · Rev. ${item.revision}` : ""}
                {"risk_type" in item ? ` · ${item.risk_type === "risk" ? "Risk" : "Opportunity"} · ${riskLabels[item.state]}` : ""}
              </option>)}
            </select>
          </label>
          {candidates?.items.length === 0 && <p role="status" className="project-help">No eligible {sourcePlural} match this search.</p>}
          {(candidateOffset > 0 || candidates?.hasMore) && <div className="project-actions">
            <button type="button" className="secondary-action compact-action" disabled={candidateOffset === 0}
              onClick={() => candidatePage(candidateOffset - contextPageSize)}>Previous {sourcePlural}</button>
            <button type="button" className="secondary-action compact-action" disabled={!candidates?.hasMore}
              onClick={() => candidatePage(candidateOffset + contextPageSize)}>More {sourcePlural}</button>
          </div>}
        </>}
        <label>{editing === "add" ? (source === "risk" ? "How this risk or opportunity relates to the requirement"
          : `How this ${source} addresses the requirement`) : "Reason for withdrawal"}
          <textarea name="note" rows={2} maxLength={600} required />
        </label>
      </fieldset>
      {record.status === "active" && <p className="project-help">Changing {source === "evidence" ? "an" : "a"} {source} link sends this party back for independent review.</p>}
      <div className="project-actions">
        <button className="primary-action compact-action" type="submit" disabled={busy || stale || locked || (editing === "add" && !selection)}>
          {busy ? "Saving…" : editing === "add" ? `Save ${source} link` : "Withdraw link"}
        </button>
        <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => {
          setEditing(null); setError("");
        }}>Cancel</button>
      </div>
    </form>}
    {links && links.items.length > 0 && <ul className="project-reference-list">
      {links.items.map(link => {
        const details = linkDetails(link);
        return <li className="project-reference-kind" key={link.id}>
        <h6>{details.code} · {details.name}</h6>
        <p className="project-help">
          {link.removed_at ? "Withdrawn" : details.status} · {details.version}
          {!link.requirement_current && " · Earlier requirement version"}
        </p>
        <p className="project-notes"><strong>{link.requirement_snapshot.statement}</strong><br />{link.rationale}</p>
        {"document_id" in link && <details className="project-help">
          <summary>Document fingerprint</summary><code className="project-reference-hash">{link.file_sha256}</code>
        </details>}
        {"evidence_id" in link && <p className="project-help">Accepted{" "}
          <time dateTime={link.accepted_at}>{new Date(link.accepted_at).toLocaleDateString()}</time>
        </p>}
        {"risk_id" in link && <p className="project-help">
          {link.risk_type === "risk" ? "Risk" : "Opportunity"} · State when linked: {riskLabels[link.linked_risk_state]}
          {link.risk_changed && " · Register has changed"}
        </p>}
        <p className="project-help">Linked at party version {link.linked_party_version}</p>
        {link.removed_at ? <p className="project-notes">Withdrawn at party version {link.removed_party_version} · {link.removal_reason}</p>
          : mayWrite && <button className="secondary-action compact-action" disabled={busy || stale || locked || editing !== null}
            type="button" onClick={() => { setError(""); setEditing(link); }}>
            Withdraw {details.code}
          </button>}
      </li>;
      })}
    </ul>}
    {(linkOffset > 0 || links?.hasMore) && <nav className="project-actions" aria-label={`${sourceLabel} link pages`}>
      <button type="button" className="secondary-action compact-action" disabled={linkOffset === 0 || editing !== null} onClick={() => {
        setLinks(null); setLinkOffset(value => value - contextPageSize);
      }}>Previous links</button>
      <button type="button" className="secondary-action compact-action" disabled={!links?.hasMore || editing !== null} onClick={() => {
        setLinks(null); setLinkOffset(value => value + contextPageSize);
      }}>Next links</button>
    </nav>}
  </section>;
}
