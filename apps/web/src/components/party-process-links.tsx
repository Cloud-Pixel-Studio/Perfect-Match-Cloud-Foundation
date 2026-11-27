"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  changePartyProcessLink, ContextError, contextPageSize, partyProcessCandidates, partyProcessLinks,
  trimRequirementText, type ContextRecord, type ContextScope, type PartyProcessCommand, type PartyProcessLink,
} from "../lib/qms-context";

const processLabels = {
  current: "Current process version",
  changed: "Process has a newer version",
  archived: "Process archived",
  unavailable: "Current process unavailable",
};

export function PartyProcessLinks({ scope, record, canManage, locked, onBusy, onChanged, onAccessFailure }: {
  scope: ContextScope;
  record: ContextRecord;
  canManage: boolean;
  locked: boolean;
  onBusy: (busy: boolean) => void;
  onChanged: (kind: PartyProcessCommand["kind"]) => void;
  onAccessFailure: (error: ContextError) => void;
}) {
  const [links, setLinks] = useState<Awaited<ReturnType<typeof partyProcessLinks>> | null>(null);
  const [linkOffset, setLinkOffset] = useState(0);
  const [candidates, setCandidates] = useState<Awaited<ReturnType<typeof partyProcessCandidates>> | null>(null);
  const [candidateOffset, setCandidateOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchRevision, setSearchRevision] = useState(0);
  const [selection, setSelection] = useState("");
  const [editing, setEditing] = useState<"add" | PartyProcessLink | null>(null);
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState("");
  const command = useRef<AbortController | null>(null);
  const requirements = record.party_requirements?.filter(item => item.disposition === "addressed_by_qms") ?? [];
  const mayWrite = canManage && record.status !== "retired";

  useEffect(() => () => {
    if (command.current) {
      command.current.abort();
      onBusy(false);
    }
  }, [onBusy]);

  useEffect(() => {
    const controller = new AbortController();
    void partyProcessLinks(scope, record, linkOffset, controller.signal).then(page => {
      if (!controller.signal.aborted) setLinks(page);
    }).catch(cause => {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        onAccessFailure(cause);
        return;
      }
      setStale(true);
      setError("Could not load process links. Refresh the register to verify the party version.");
    });
    return () => controller.abort();
  }, [scope, record, linkOffset, onAccessFailure]);

  useEffect(() => {
    if (editing !== "add" || !mayWrite) return;
    const controller = new AbortController();
    void partyProcessCandidates(scope, record, search, candidateOffset, controller.signal).then(page => {
      if (!controller.signal.aborted) setCandidates(page);
    }).catch(cause => {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        onAccessFailure(cause);
        return;
      }
      setError("Could not load eligible processes. Retry the search or refresh the register.");
    });
    return () => controller.abort();
  }, [scope, record, editing, mayWrite, search, candidateOffset, searchRevision, onAccessFailure]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || command.current || !mayWrite || stale || locked) return;
    const fields = new FormData(event.currentTarget);
    const reason = trimRequirementText(String(fields.get("note") ?? ""));
    if (!reason) {
      setError("Enter a reason before saving.");
      return;
    }
    let change: PartyProcessCommand;
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
      await changePartyProcessLink(scope, record, change, decodeURIComponent(token), controller.signal);
      if (!controller.signal.aborted) onChanged(change.kind);
    } catch (cause) {
      if (controller.signal.aborted) return;
      if (cause instanceof ContextError && (cause.status === 401 || cause.status === 403 || cause.scopeChanged)) {
        onAccessFailure(cause);
      } else if (cause instanceof ContextError && cause.status === 422) {
        setError("Check the selected process, requirement and rationale.");
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

  return <section className="project-summary party-process-links" aria-label="Process links">
    <h5>Process links</h5>
    {error && <p role="alert" className="project-feedback">{error}</p>}
    {!links && !error && <p role="status">Loading process links…</p>}
    {links?.items.length === 0 && <p role="status">No processes have been linked.</p>}
    {mayWrite && editing === null && requirements.length > 0 &&
      <button className="primary-action compact-action" type="button" disabled={busy || stale || locked} onClick={showAdd}>Link a process</button>}
    {mayWrite && requirements.length === 0 && <p className="project-help">Decide which requirements the QMS will address to link a process.</p>}
    {editing === "add" && <div className="project-toolbar">
      <label>Find a process
        <input type="search" maxLength={120} value={searchInput} disabled={busy}
          onChange={event => setSearchInput(event.target.value)} />
      </label>
      <button type="button" className="secondary-action compact-action" disabled={busy} onClick={() => {
        candidatePage(0); setSearch(searchInput.trim()); setError(""); setSearchRevision(value => value + 1);
      }}>Search processes</button>
    </div>}
    {editing !== null && <form className="project-summary" onSubmit={save}>
      <fieldset disabled={busy || locked} className="context-fields">
        <legend>{editing === "add" ? "New process link" : `Withdraw link to ${editing.process_code}`}</legend>
        {editing === "add" && <>
          <label>Requirement
            <select name="requirement" required defaultValue={requirements.length === 1 ? requirements[0].id : ""}>
              <option value="" disabled>Select a requirement</option>
              {requirements.map(item => <option key={item.id} value={item.id}>{item.statement}</option>)}
            </select>
          </label>
          <label>Process
            <select name="process" required value={selection} onChange={event => setSelection(event.target.value)}>
              <option value="" disabled>{candidates ? "Select an active process" : "Loading processes…"}</option>
              {candidates?.items.map(item => <option value={item.id} key={item.id}>{item.code} · {item.name}</option>)}
            </select>
          </label>
          {candidates?.items.length === 0 && <p role="status" className="project-help">No active processes match this search.</p>}
          {(candidateOffset > 0 || candidates?.hasMore) && <div className="project-actions">
            <button type="button" className="secondary-action compact-action" disabled={candidateOffset === 0}
              onClick={() => candidatePage(candidateOffset - contextPageSize)}>Previous processes</button>
            <button type="button" className="secondary-action compact-action" disabled={!candidates?.hasMore}
              onClick={() => candidatePage(candidateOffset + contextPageSize)}>More processes</button>
          </div>}
        </>}
        <label>{editing === "add" ? "How this process addresses the requirement" : "Reason for withdrawal"}
          <textarea name="note" rows={2} maxLength={600} required />
        </label>
      </fieldset>
      {record.status === "active" && <p className="project-help">Changing a process link sends this party back for independent review.</p>}
      <div className="project-actions">
        <button className="primary-action compact-action" type="submit" disabled={busy || stale || locked || (editing === "add" && !selection)}>
          {busy ? "Saving…" : editing === "add" ? "Save process link" : "Withdraw link"}
        </button>
        <button className="secondary-action compact-action" type="button" disabled={busy} onClick={() => {
          setEditing(null); setError("");
        }}>Cancel</button>
      </div>
    </form>}
    {links && links.items.length > 0 && <ul className="project-reference-list">
      {links.items.map(link => <li className="project-reference-kind" key={link.id}>
        <h6>{link.process_code} · {link.process_name}</h6>
        <p className="project-help">
          {link.removed_at ? "Withdrawn" : processLabels[link.process_state]} · Linked process version {link.process_version}
          {!link.requirement_current && " · Earlier requirement version"}
        </p>
        <p className="project-notes"><strong>{link.requirement_snapshot.statement}</strong><br />{link.rationale}</p>
        <p className="project-help">Linked at party version {link.linked_party_version}</p>
        {link.removed_at ? <p className="project-notes">Withdrawn at party version {link.removed_party_version} · {link.removal_reason}</p>
          : mayWrite && <button className="secondary-action compact-action" disabled={busy || stale || locked || editing !== null}
            type="button" onClick={() => { setError(""); setEditing(link); }}>
            Withdraw {link.process_code}
          </button>}
      </li>)}
    </ul>}
    {(linkOffset > 0 || links?.hasMore) && <nav className="project-actions" aria-label="Process link pages">
      <button type="button" className="secondary-action compact-action" disabled={linkOffset === 0 || editing !== null} onClick={() => {
        setLinks(null); setLinkOffset(value => value - contextPageSize);
      }}>Previous links</button>
      <button type="button" className="secondary-action compact-action" disabled={!links?.hasMore || editing !== null} onClick={() => {
        setLinks(null); setLinkOffset(value => value + contextPageSize);
      }}>Next links</button>
    </nav>}
  </section>;
}
