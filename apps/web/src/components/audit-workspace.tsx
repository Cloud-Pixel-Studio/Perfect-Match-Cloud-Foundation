"use client";

import { ArrowDown, FileClock, ListFilter, RefreshCw, ScrollText, Search, UsersRound } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { auditLabel, buildAuditDiff, formatAuditValue, type AuditValues } from "../lib/audit-view";
import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type AuditEvent = {
  id: string;
  occurred_at: string;
  actor_display_name: string;
  actor_role: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  request_id: string;
  schema_version: number;
  changed_fields: string[];
  old_values: AuditValues;
  new_values: AuditValues;
};

type AuditPage = { items: AuditEvent[]; next_cursor: string | null };

export function AuditWorkspace() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");
  const requestRevision = useRef(0);

  const load = useCallback(async ({ append = false, cursor = "" }: { append?: boolean; cursor?: string } = {}) => {
    const revision = ++requestRevision.current;
    setLoading(true);
    setError("");
    if (!append) {
      setEvents([]);
      setNextCursor(null);
      setLoaded(false);
    }
    const params = new URLSearchParams({ limit: "20" });
    if (cursor) params.set("cursor", cursor);
    if (action) params.set("action", action);
    if (resourceType) params.set("resource_type", resourceType);
    try {
      const response = await fetch(`/api/identity/audit/events?${params}`, { credentials: "include" });
      if (!response.ok) throw new Error(response.status === 403 ? "Audit trail access is restricted to authorized roles." : "Audit history is temporarily unavailable.");
      const page = (await response.json()) as AuditPage;
      if (revision !== requestRevision.current) return;
      setEvents((current) => append ? [...current, ...page.items.filter((item) => !current.some((row) => row.id === item.id))] : page.items);
      setNextCursor(page.next_cursor);
      setLoaded(true);
    } catch (cause) {
      if (revision === requestRevision.current) setError(cause instanceof Error ? cause.message : "Audit history is temporarily unavailable.");
    } finally {
      if (revision === requestRevision.current) setLoading(false);
    }
  }, [action, resourceType]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => {
      window.clearTimeout(timer);
      requestRevision.current += 1;
    };
  }, [load]);

  const actionOptions = useMemo(() => [...new Set([action, ...events.map((event) => event.action)].filter(Boolean))].sort(), [action, events]);
  const resourceOptions = useMemo(() => [...new Set([resourceType, ...events.map((event) => event.resource_type)].filter(Boolean))].sort(), [events, resourceType]);
  const visibleEvents = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return events;
    return events.filter((event) => [
      event.action,
      event.resource_type,
      event.actor_display_name,
      event.actor_role,
      event.request_id,
      event.resource_id ?? "",
      ...event.changed_fields,
    ].some((value) => value.toLowerCase().includes(normalized)));
  }, [events, query]);
  const actorCount = new Set(events.map((event) => event.actor_display_name)).size;
  const changedCount = events.reduce((total, event) => total + event.changed_fields.length, 0);

  function clearFilters() {
    setQuery("");
    setAction("");
    setResourceType("");
  }

  function preventSubmit(event: FormEvent) {
    event.preventDefault();
  }

  return (
    <section className="audit-panel" aria-labelledby="audit-heading" aria-busy={loading}>
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">Compliance history</p>
          <h2 id="audit-heading"><ScrollText aria-hidden="true" size={21} /> Audit trail</h2>
          <p className="workspace-subtitle">Trace decisions, actors and field-level changes without altering the underlying record.</p>
        </div>
        <button className="secondary-action compact-action" disabled={loading} onClick={() => void load()} type="button">
          <RefreshCw aria-hidden="true" size={16} /> Refresh history
        </button>
      </div>

      <div className="audit-metrics" aria-label="Loaded audit history summary">
        <article><FileClock aria-hidden="true" size={19} /><span><strong>{events.length}</strong><small>Events loaded</small></span></article>
        <article><UsersRound aria-hidden="true" size={19} /><span><strong>{actorCount}</strong><small>Recorded actors</small></span></article>
        <article><ListFilter aria-hidden="true" size={19} /><span><strong>{changedCount}</strong><small>Field changes</small></span></article>
      </div>

      <form className="audit-filters" aria-label="Filter audit history" onSubmit={preventSubmit}>
        <label className="audit-search"><span>Search loaded history</span><span><Search aria-hidden="true" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Actor, action, request or field" /></span></label>
        <label><span>Action</span><select value={action} onChange={(event) => setAction(event.target.value)}><option value="">All actions</option>{actionOptions.map((item) => <option key={item} value={item}>{auditLabel(item)}</option>)}</select></label>
        <label><span>Resource</span><select value={resourceType} onChange={(event) => setResourceType(event.target.value)}><option value="">All resources</option>{resourceOptions.map((item) => <option key={item} value={item}>{auditLabel(item)}</option>)}</select></label>
        {(query || action || resourceType) && <button className="secondary-action compact-action" onClick={clearFilters} type="button">Clear filters</button>}
      </form>

      {loading && !loaded && <RecordWorkspaceSkeleton label="Loading audit history" />}
      {error && <p className="denied-state" role="alert">{error}</p>}
      {loaded && !error && visibleEvents.length === 0 && <div className="empty-state"><Search aria-hidden="true" size={21} /><div><strong>{events.length ? "No events match these filters" : "No audit events recorded"}</strong><p>{events.length ? "Clear or adjust the filters to inspect other activity." : "Recorded changes for this organization will appear here."}</p></div></div>}

      {visibleEvents.length > 0 && <div className="audit-list">
        {visibleEvents.map((event) => {
          const rows = buildAuditDiff(event.changed_fields, event.old_values, event.new_values);
          return <details className="audit-event" key={event.id}>
            <summary>
              <span className="audit-event-icon"><ScrollText aria-hidden="true" size={17} /></span>
              <span className="audit-event-title"><strong>{auditLabel(event.action)}</strong><small>{event.actor_display_name} · {auditLabel(event.actor_role)} · {auditLabel(event.resource_type)}</small></span>
              <span className="audit-event-meta"><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time><small>{rows.filter((row) => row.changed).length} changed fields</small></span>
            </summary>
            <div className="audit-event-body">
              <dl className="audit-technical-facts">
                <div><dt>Resource</dt><dd>{event.resource_id ?? "Not associated"}</dd></div>
                <div><dt>Request ID</dt><dd>{event.request_id}</dd></div>
                <div><dt>Schema</dt><dd>Version {event.schema_version}</dd></div>
              </dl>
              {rows.length === 0 ? <p className="audit-no-diff">This event records an action without field-level values.</p> : <div className="audit-diff" role="table" aria-label={`Field changes for ${auditLabel(event.action)}`}>
                <div className="audit-diff-header" role="row"><span role="columnheader">Field</span><span role="columnheader">Before</span><span role="columnheader">After</span></div>
                {rows.map((row) => <div className={row.changed ? "audit-diff-row changed" : "audit-diff-row"} role="row" key={row.field}>
                  <strong role="rowheader">{auditLabel(row.field)}</strong>
                  <span className="audit-diff-cell" role="cell"><small>Before</small><pre>{formatAuditValue(row.before)}</pre></span>
                  <span className="audit-diff-cell" role="cell"><small>After</small><pre>{formatAuditValue(row.after)}</pre></span>
                </div>)}
              </div>}
            </div>
          </details>;
        })}
      </div>}

      {nextCursor && !query && <button className="audit-load-more secondary-action" disabled={loading} onClick={() => void load({ append: true, cursor: nextCursor })} type="button">
        <ArrowDown aria-hidden="true" size={16} /> {loading ? "Loading history…" : "Load older events"}
      </button>}
      {loaded && <p className="qms-history-caption">Audit history is append-only. Filters affect presentation only and never alter recorded evidence.</p>}
    </section>
  );
}
