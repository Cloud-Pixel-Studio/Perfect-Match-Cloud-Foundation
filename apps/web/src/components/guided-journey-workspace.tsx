"use client";

import { ArrowLeft, ArrowRight, ArrowRightLeft, BookOpen, Building2, ChevronRight, ClipboardCheck, FolderInput, Info, Layers3, LockKeyhole, LogIn, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";

import { journeys, observeGuideStep } from "../lib/guided-journeys";
import { GuideAccessError, loadGuideSnapshot, loadGuideUnits, type GuideResource, type GuideSnapshot, type GuideUnit } from "../lib/guided-journey-data";
import type { WorkspaceId } from "../lib/workspace-navigation";

type Props = {
  tenantId: string;
  userId: string;
  preferredUnitId?: string;
  onUnitChange?: (unitId: string) => void;
  onNavigate: (id: WorkspaceId) => void;
};

const journeyIcons = [BookOpen, Layers3, ArrowRightLeft, FolderInput, ClipboardCheck, Building2];
const resourceWorkspaces: Record<GuideResource, WorkspaceId> = {
  processes: "processes", documents: "documents", implementations: "controls", risks: "risks",
  nonconformities: "nonconformities", capas: "capa", audits: "internal-audits",
};
const workspaceLabels: Partial<Record<WorkspaceId, string>> = {
  processes: "Processes", documents: "Documents", controls: "Controls & evidence", risks: "Risks & opportunities",
  nonconformities: "Nonconformities", capa: "Corrective actions", "internal-audits": "Internal audits",
};

function readable(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

export function GuidedJourneyWorkspace(props: Props) {
  const [journeyId, setJourneyId] = useState(journeys[0].id);
  const [stepIndex, setStepIndex] = useState(0);
  // A changed actor, company or externally selected unit must never render the previous snapshot.
  return <GuideScope key={JSON.stringify([props.tenantId, props.userId, props.preferredUnitId ?? ""])} {...props} journeyId={journeyId} setJourneyId={setJourneyId} stepIndex={stepIndex} setStepIndex={setStepIndex} />;
}

function GuideScope({ tenantId, userId, preferredUnitId, onUnitChange, onNavigate, journeyId, setJourneyId, stepIndex, setStepIndex }: Props & {
  journeyId: (typeof journeys)[number]["id"];
  setJourneyId: (value: (typeof journeys)[number]["id"]) => void;
  stepIndex: number;
  setStepIndex: (value: number) => void;
}) {
  const [units, setUnits] = useState<GuideUnit[]>([]);
  const [unitsLimited, setUnitsLimited] = useState(false);
  const [unitsLoading, setUnitsLoading] = useState(true);
  const [unitError, setUnitError] = useState(false);
  const [unitId, setUnitId] = useState("");
  const [snapshot, setSnapshot] = useState<GuideSnapshot | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState(false);
  const [accessError, setAccessError] = useState<number | null>(null);
  const [unitRevision, setUnitRevision] = useState(0);
  const [snapshotRevision, setSnapshotRevision] = useState(0);
  const unitsRequest = useRef<AbortController | null>(null);
  const snapshotRequest = useRef<AbortController | null>(null);
  const snapshotSequence = useRef(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const detailHeading = useRef<HTMLHeadingElement | null>(null);

  const journey = journeys.find((item) => item.id === journeyId) ?? journeys[0];
  const step = journey.steps[Math.min(stepIndex, journey.steps.length - 1)];
  const unit = units.find((item) => item.id === unitId);
  const observation = observeGuideStep(step, snapshot);
  const canOpen = Boolean(unit && snapshot && !snapshotLoading && !snapshotError && !accessError && !step.productGap && step.resource && step.workspace && observation.kind === "loaded" && resourceWorkspaces[step.resource] === step.workspace);

  const invalidateAccess = useCallback((status: number) => {
    snapshotSequence.current += 1;
    unitsRequest.current?.abort();
    snapshotRequest.current?.abort();
    setSnapshot(null);
    setUnits([]);
    setUnitsLimited(false);
    setUnitId("");
    setUnitsLoading(false);
    setSnapshotLoading(false);
    setSnapshotError(false);
    setUnitError(false);
    setAccessError(status);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    unitsRequest.current = controller;
    void loadGuideUnits(tenantId, controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setUnits(result.units);
      setUnitsLimited(result.limited);
      setUnitsLoading(false);
      // An explicit accessible preference is the only automatic selection.
      if (preferredUnitId && result.units.some((item) => item.id === preferredUnitId)) {
        setSnapshotLoading(true);
        setUnitId(preferredUnitId);
      }
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return;
      if (cause instanceof GuideAccessError && (cause.status === 401 || cause.status === 403)) {
        invalidateAccess(cause.status);
      } else {
        setUnits([]);
        setUnitsLoading(false);
        setUnitError(true);
      }
    });
    return () => controller.abort();
  }, [tenantId, preferredUnitId, unitRevision, invalidateAccess]);

  useEffect(() => {
    if (!unitId) return;
    const controller = new AbortController();
    snapshotRequest.current = controller;
    const sequence = ++snapshotSequence.current;
    void loadGuideSnapshot({ tenantId, userId, unitId }, controller.signal).then((result) => {
      if (controller.signal.aborted || sequence !== snapshotSequence.current) return;
      if (result.tenantId !== tenantId || result.userId !== userId || result.unitId !== unitId) throw new Error("Snapshot scope changed");
      setSnapshot(result);
      setSnapshotLoading(false);
    }).catch((cause: unknown) => {
      if (controller.signal.aborted || sequence !== snapshotSequence.current) return;
      if (cause instanceof GuideAccessError && (cause.status === 401 || cause.status === 403)) {
        invalidateAccess(cause.status);
      } else {
        setSnapshot(null);
        setSnapshotLoading(false);
        setSnapshotError(true);
      }
    });
    return () => controller.abort();
  }, [tenantId, userId, unitId, snapshotRevision, invalidateAccess]);

  function clearSnapshot() {
    snapshotSequence.current += 1;
    snapshotRequest.current?.abort();
    setSnapshot(null);
    setSnapshotError(false);
  }

  function changeUnit(value: string) {
    clearSnapshot();
    setUnitId(value);
    setSnapshotLoading(Boolean(value));
    onUnitChange?.(value);
  }

  function refreshSnapshot() {
    clearSnapshot();
    setSnapshotLoading(true);
    setSnapshotRevision((value) => value + 1);
  }

  function reloadAccess() {
    clearSnapshot();
    unitsRequest.current?.abort();
    setUnits([]);
    setUnitsLimited(false);
    setUnitId("");
    setAccessError(null);
    setUnitError(false);
    setUnitsLoading(true);
    setSnapshotLoading(false);
    setUnitRevision((value) => value + 1);
  }

  function selectJourney(index: number, focus = false) {
    setJourneyId(journeys[index].id);
    setStepIndex(0);
    if (focus) tabRefs.current[index]?.focus();
  }

  function journeyKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    let next = index;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % journeys.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index + journeys.length - 1) % journeys.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = journeys.length - 1;
    else return;
    event.preventDefault();
    selectJourney(next, true);
  }

  function moveStep(index: number) {
    setStepIndex(index);
    detailHeading.current?.focus({ preventScroll: true });
    detailHeading.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }

  const observationLabel = step.productGap ? "Feature pending" : accessError ? "Access required" : snapshotLoading ? "Checking records…" : snapshotError ? "Could not verify" : observation.kind === "loaded" ? (observation.records.length ? "Records found" : "No records found") : observation.kind === "restricted" ? "Access required" : observation.kind === "unavailable" ? "Could not verify" : "Choose a unit";

  return <section className="guided-workspace" aria-labelledby="implementation-guide-heading">
    <header className="guide-heading">
      <div><p className="eyebrow">A clear path through your quality system</p><h2 id="implementation-guide-heading">Implementation guide</h2><p>Choose your starting point. Follow practical steps, inspect current records and see what needs a separate review.</p></div>
      <span className="guide-heading-mark"><BookOpen aria-hidden="true" size={26} /></span>
    </header>

    <div className="guide-scope">
      <div className="guide-unit-control"><label htmlFor="guide-unit">Organizational unit</label><select id="guide-unit" value={unitId} disabled={unitsLoading || Boolean(accessError)} onChange={(event) => changeUnit(event.target.value)} aria-describedby="guide-scope-explanation"><option value="">{unitsLoading ? "Loading units…" : "Select a unit"}</option>{units.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></div>
      <div className="guide-scope-description"><strong>{unit ? `${unit.code} · ${unit.name}` : "Read the guide at your own pace"}</strong><p id="guide-scope-explanation">{unit ? "Observations cover this unit’s records. They are not linked to a project and do not evaluate compliance or complete a step." : "Select a unit to inspect authorized records. All journey instructions remain available without record access."}</p>{snapshot && <p className="guide-timestamp">Snapshot updated <time dateTime={snapshot.fetchedAt}>{new Date(snapshot.fetchedAt).toLocaleString()}</time></p>}</div>
      <button className="secondary-action compact-action guide-refresh" disabled={!unit || snapshotLoading || Boolean(accessError)} type="button" onClick={refreshSnapshot}><RefreshCw aria-hidden="true" size={16} />Refresh snapshot</button>
    </div>
    {unitsLimited && <p className="guide-inline-note">Showing the first 100 accessible units. This list may be partial.</p>}
    {!unitsLoading && !unitError && !accessError && units.length === 0 && <p className="guide-inline-note" role="status">No accessible organizational units were found. You can still follow every journey below.</p>}
    {preferredUnitId && !unitsLoading && !unitError && !accessError && !unit && units.length > 0 && <p className="guide-inline-note">The preferred unit is not in the accessible unit list. Select a unit to inspect records.</p>}
    {unitError && <div className="guide-notice" role="alert"><Info aria-hidden="true" size={21} /><div><strong>Could not verify organizational units</strong><p>Unit access could not be loaded. The guide remains available.</p><button className="secondary-action compact-action" onClick={reloadAccess} type="button">Reload access</button></div></div>}
    {accessError && <div className="guide-notice" role="alert"><LockKeyhole aria-hidden="true" size={22} /><div><strong>{accessError === 401 ? "Your session has expired" : "Access required"}</strong><p>{accessError === 401 ? "Sign in again to verify current access and load records." : "Your access changed. Reload access before inspecting unit records."}</p>{accessError === 401 ? <>
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- OIDC login requires a full browser navigation, without prefetch. */}
      <a className="primary-action compact-action" href="/api/identity/auth/login"><LogIn aria-hidden="true" size={16} />Sign in again</a>
    </> : <button className="secondary-action compact-action" onClick={reloadAccess} type="button">Reload access</button>}</div></div>}

    <div className="guide-case-heading"><h3>What brings you here?</h3><p>Six journeys, built around your starting point.</p></div>
    <div className="guide-cases" role="tablist" aria-label="QMS journeys">{journeys.map((item, index) => {
      const Icon = journeyIcons[index] ?? BookOpen;
      return <button key={item.id} ref={(element) => { tabRefs.current[index] = element; }} id={`guide-tab-${item.id}`} role="tab" aria-selected={journey.id === item.id} aria-controls="guide-journey-panel" tabIndex={journey.id === item.id ? 0 : -1} type="button" onClick={() => selectJourney(index)} onKeyDown={(event) => journeyKey(event, index)}><span className="guide-case-icon"><Icon aria-hidden="true" size={19} /></span><strong>{item.title}</strong><span>{item.summary}</span><small>{item.steps.length} guided steps <ChevronRight aria-hidden="true" size={14} /></small></button>;
    })}</div>

    <div id="guide-journey-panel" role="tabpanel" aria-labelledby={`guide-tab-${journey.id}`} className="guide-journey-panel" tabIndex={0}>
      <div className="guide-journey-heading"><div><p className="eyebrow">Your selected journey</p><h3>{journey.title}</h3><p>{journey.outcome}</p></div><span className="guide-step-counter">Step {stepIndex + 1} of {journey.steps.length}</span></div>
      <div className="guide-body">
        <nav className="guide-step-navigation" aria-label={`${journey.title} steps`}><p className="guide-small-label">Follow the sequence</p><ol>{journey.steps.map((item, index) => <li key={item.id}><button type="button" aria-current={index === stepIndex ? "step" : undefined} onClick={() => moveStep(index)}><span className="guide-step-number" aria-hidden="true">{index + 1}</span><span>{item.title}{item.productGap && <small>Feature pending</small>}</span>{index === stepIndex && <ChevronRight aria-hidden="true" size={16} />}</button></li>)}</ol><p className="guide-step-note">Steps are guidance. Browsing a step does not mark work as complete.</p></nav>
        <article className="guide-step-detail" aria-labelledby="guide-step-heading">
          <div className="guide-detail-heading"><p className="guide-small-label">Step {stepIndex + 1}</p><h4 id="guide-step-heading" ref={detailHeading} tabIndex={-1}>{step.title}</h4><h5>Why this matters</h5><p>{step.why}</p></div>
          <section className="guide-instructions" aria-labelledby="guide-instructions-heading"><h5 id="guide-instructions-heading">What to do</h5><ol>{step.instructions.map((instruction, index) => <li key={`${step.id}-${index}`}>{instruction}</li>)}</ol></section>
          <dl className="guide-outputs"><div><dt>Expected output</dt><dd>{step.expected}</dd></div><div><dt>Review before moving on</dt><dd>{step.doneWhen}</dd></div></dl>
          {step.limitation && <p className="guide-limitation"><Info aria-hidden="true" size={17} />{step.limitation}</p>}

          <section className="guide-observation" aria-labelledby="guide-observation-heading" aria-busy={snapshotLoading && !step.productGap}>
            <div className="guide-observation-heading"><h5 id="guide-observation-heading">Current unit observations</h5><span className={`guide-observation-badge${step.productGap ? " is-pending" : ""}`}>{observationLabel}</span></div>
            {step.productGap ? <p>{step.productGap}</p> : accessError ? <p>Records were cleared. {accessError === 401 ? "Sign in again to verify your session." : "Reload access to verify current responsibilities."}</p> : snapshotLoading ? <p role="status">Checking the selected unit’s current records…</p> : snapshotError ? <p role="status">The snapshot could not be verified. Refresh the snapshot to try again; previous observations have been cleared.</p> : <>
              <p>{observation.message}</p>
              {observation.kind === "loaded" && <>
                {observation.limited && <p className="guide-sample-note">Partial sample: first 50 records only. Counts describe this sample, not the total for this unit.</p>}
                {observation.records.length > 0 && <><p className="guide-qualified-count">{observation.records.length} {observation.limited ? "sampled " : ""}records · {observation.qualified} meet the observed record-state condition. Review relevance and evidence separately.</p><details className="guide-records"><summary>Inspect {observation.records.length} {observation.limited ? "sampled " : ""}records</summary><ul tabIndex={0} aria-label="Observed unit records">{observation.records.map((record) => <li key={record.id}><div><strong>{record.code}</strong><span>{record.name}</span></div><span className="guide-record-state">{readable(record.state)}<small>{record.qualified ? "Meets record-state condition" : "Review record state"}</small></span></li>)}</ul></details></>}
              </>}
            </>}
            {canOpen && step.workspace && <button className="primary-action compact-action guide-open-module" type="button" onClick={() => { if (!canOpen || !step.workspace) return; onUnitChange?.(unitId); onNavigate(step.workspace); }}>Open {workspaceLabels[step.workspace] ?? readable(step.workspace)}<ArrowRight aria-hidden="true" size={16} /></button>}
          </section>
          <nav className="guide-step-pagination" aria-label="Journey step navigation"><button className="secondary-action compact-action" disabled={stepIndex === 0} onClick={() => moveStep(stepIndex - 1)} type="button"><ArrowLeft aria-hidden="true" size={16} />Previous step</button><span>{stepIndex + 1} / {journey.steps.length}</span><button className="secondary-action compact-action" disabled={stepIndex === journey.steps.length - 1} onClick={() => moveStep(stepIndex + 1)} type="button">Next step<ArrowRight aria-hidden="true" size={16} /></button></nav>
        </article>
      </div>
    </div>
  </section>;
}
