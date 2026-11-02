"use client";

import { ChevronDown, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

export const fishboneCategories = ["people", "process", "equipment", "materials", "measurement", "environment"] as const;

export type FishboneCause = {
  statement: string;
  evidence: string;
  rationale: string;
  confirmed: boolean;
};

export type FishboneData = Record<(typeof fishboneCategories)[number], FishboneCause[]>;

const blankCause = (): FishboneCause => ({ statement: "", evidence: "", rationale: "", confirmed: false });

export function normalizeFishboneData(raw: Record<string, unknown>): FishboneData {
  return Object.fromEntries(fishboneCategories.map((category) => {
    const value = raw[category];
    if (typeof value === "string") return [category, value.trim() ? [{ ...blankCause(), statement: value }] : []];
    if (!Array.isArray(value)) return [category, []];
    return [category, value.map((cause) => {
      const item = typeof cause === "object" && cause !== null ? cause as Record<string, unknown> : {};
      return {
        statement: typeof item.statement === "string" ? item.statement : "",
        evidence: typeof item.evidence === "string" ? item.evidence : "",
        rationale: typeof item.rationale === "string" ? item.rationale : "",
        confirmed: item.confirmed === true,
      };
    })];
  })) as FishboneData;
}

export function FishboneCauses({ data, disabled }: { data: Record<string, unknown>; disabled: boolean }) {
  const [causes, setCauses] = useState<FishboneData>(() => normalizeFishboneData(data));
  const [expanded, setExpanded] = useState<Record<keyof FishboneData, boolean>>(() => {
    const initial = normalizeFishboneData(data);
    return Object.fromEntries(fishboneCategories.map((category) => [category, initial[category].length > 0])) as Record<keyof FishboneData, boolean>;
  });

  function change(category: keyof FishboneData, index: number, patch: Partial<FishboneCause>) {
    setCauses((current) => ({
      ...current,
      [category]: current[category].map((cause, position) => position === index ? { ...cause, ...patch } : cause),
    }));
  }

  return <div className="fishbone-editor">
    <input type="hidden" name="fishbone_data" value={JSON.stringify(causes)} />
    <p className="qms-history-caption">Record each possible cause separately. Confirm only causes supported by evidence and a reasoned conclusion.</p>
    {fishboneCategories.map((category) => <details className="ncr-form-section ncr-wide fishbone-category" key={category} open={expanded[category]} onToggle={(event) => {
      const open = event.currentTarget.open;
      setExpanded((current) => current[category] === open ? current : { ...current, [category]: open });
    }}>
      <summary><strong>{category[0].toUpperCase() + category.slice(1)}</strong><span>{causes[category].length} causes · {causes[category].filter((cause) => cause.confirmed).length} confirmed</span><ChevronDown aria-hidden="true" size={17} /></summary>
      {causes[category].map((cause, index) => <div className="fishbone-cause" key={`${category}-${index}`}>
        <div className="fishbone-cause-heading"><strong>Cause {index + 1}</strong><button className="secondary-action compact-action" type="button" disabled={disabled} onClick={() => setCauses((current) => ({ ...current, [category]: current[category].filter((_, position) => position !== index) }))}><Trash2 aria-hidden="true" size={15} /> Remove</button></div>
        <div className="ncr-form-grid">
          <label className="ncr-wide">Cause statement<textarea value={cause.statement} onChange={(event) => change(category, index, { statement: event.target.value })} maxLength={1000} rows={2} /></label>
          <label className="ncr-wide">Supporting evidence<textarea value={cause.evidence} onChange={(event) => change(category, index, { evidence: event.target.value })} maxLength={2000} rows={2} /></label>
          <label className="ncr-wide">Reason for confirmation<textarea value={cause.rationale} onChange={(event) => change(category, index, { rationale: event.target.value })} maxLength={2000} rows={2} /></label>
          <label className="ncr-check fishbone-confirmed"><input type="checkbox" checked={cause.confirmed} onChange={(event) => change(category, index, { confirmed: event.target.checked })} /> Confirmed cause</label>
        </div>
      </div>)}
      <button className="secondary-action compact-action fishbone-add" type="button" disabled={disabled || causes[category].length >= 10} onClick={() => setCauses((current) => ({ ...current, [category]: [...current[category], blankCause()] }))}><Plus aria-hidden="true" size={15} /> Add cause</button>
    </details>)}
  </div>;
}
