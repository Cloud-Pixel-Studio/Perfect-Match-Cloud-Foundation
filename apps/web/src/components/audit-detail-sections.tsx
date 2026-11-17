"use client";

import { ClipboardList, ShieldCheck, UsersRound } from "lucide-react";
import { type ReactNode, useId, useState } from "react";

const sections = [
  { id: "scope", label: "Scope & criteria", icon: ClipboardList },
  { id: "people", label: "People & schedule", icon: UsersRound },
  { id: "readiness", label: "Readiness", icon: ShieldCheck },
] as const;

type Section = (typeof sections)[number]["id"];

/** Keep editors mounted: section navigation must never discard a draft. */
export function AuditDetailSections({ scope, people, readiness, disabled }: {
  scope: ReactNode; people: ReactNode; readiness: ReactNode; disabled: boolean;
}) {
  const [active, setActive] = useState<Section>("scope");
  const prefix = useId();
  const content = { scope, people, readiness };

  return <div className="ia-detail-sections">
    <div className="ia-detail-navigation" role="tablist" aria-label="Audit detail sections">
      {sections.map(({ id, label, icon: Icon }, index) => <button
        key={id} type="button" role="tab" id={`${prefix}-${id}-tab`}
        aria-controls={`${prefix}-${id}-panel`} aria-selected={active === id}
        tabIndex={active === id ? 0 : -1} disabled={disabled}
        onClick={() => setActive(id)}
        onKeyDown={(event) => {
          if (disabled || event.altKey || event.ctrlKey || event.metaKey) return;
          const next = event.key === "Home" ? 0 : event.key === "End" ? sections.length - 1
            : event.key === "ArrowRight" ? (index + 1) % sections.length
            : event.key === "ArrowLeft" ? (index + sections.length - 1) % sections.length : null;
          if (next === null) return;
          event.preventDefault();
          setActive(sections[next].id);
          document.getElementById(`${prefix}-${sections[next].id}-tab`)?.focus();
        }}
      ><Icon size={16} aria-hidden="true" /><span>{label}</span></button>)}
    </div>
    {sections.map(({ id }) => <div key={id} className="ia-detail-section" role="tabpanel"
      id={`${prefix}-${id}-panel`} aria-labelledby={`${prefix}-${id}-tab`}
      hidden={active !== id} tabIndex={0}>
      {content[id]}
    </div>)}
  </div>;
}
