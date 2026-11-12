"use client";

import Image from "next/image";
import { ArrowUpRight, CheckCircle2 } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";

const views = [
  { id: "documents", label: "Document control", title: "Know which revision your team should use.", copy: "Keep the file, its revision and the review decision in one place. See how controlled information moves through the current product.", points: ["Revision and release status", "Independent review and approval history", "Private document files"], record: "DEMO-DOC-001 · Controlled procedure" },
  { id: "risks", label: "Risks & opportunities", title: "Give each risk a response and an owner.", copy: "Move from identifying exposure to following a response, while keeping the process, responsible person and assessment together.", points: ["Initial and residual assessment", "Process scope and responsibility", "Monitoring and recorded decisions"], record: "DEMO-RSK-001 · Receiving risk" },
  { id: "capa", label: "Corrective actions", title: "Connect the issue, the cause and the follow-up.", copy: "Follow corrective work through investigation, action planning, independent verification and effectiveness review.", points: ["Root-cause analysis and action planning", "Linked document and evidence references", "Controlled review and closure decisions"], record: "DEMO-CAPA-001 · Corrective action" },
] as const;

export function ProductTour() {
  const id = useId();
  const [selected, setSelected] = useState(0);
  const buttons = useRef<Array<HTMLButtonElement | null>>([]);
  const view = views[selected];

  function navigate(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % views.length;
    else if (event.key === "ArrowLeft") next = (index + views.length - 1) % views.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = views.length - 1;
    else return;
    event.preventDefault();
    setSelected(next);
    buttons.current[next]?.focus();
  }

  return (
    <div className="market-tour">
      <div className="market-tour-tabs" role="tablist" aria-label="Explore quality workflows">
        {views.map((item, index) => <button aria-controls={`${id}-panel`} aria-selected={selected === index} id={`${id}-${item.id}`} key={item.id} onClick={() => setSelected(index)} onKeyDown={(event) => navigate(event, index)} ref={(node) => { buttons.current[index] = node; }} role="tab" tabIndex={selected === index ? 0 : -1} type="button">{item.label}</button>)}
      </div>
      <div aria-labelledby={`${id}-${view.id}`} className="market-tour-panel" id={`${id}-panel`} role="tabpanel" tabIndex={0}>
        <div className="market-tour-copy"><span className="market-tour-index">0{selected + 1} / PRODUCT IN PRACTICE</span><h3>{view.title}</h3><p>{view.copy}</p><ul>{view.points.map((point) => <li key={point}><CheckCircle2 aria-hidden="true" size={17} />{point}</li>)}</ul><a href={`/brand/product/${view.id}.png`} target="_blank" rel="noopener noreferrer">Open the full capture <ArrowUpRight aria-hidden="true" size={16} /></a></div>
        <figure className="market-tour-capture"><div><Image alt={`${view.label}: real Perfect Match QMS interface with synthetic demo data`} height={view.id === "documents" ? 762 : 800} src={`/brand/product/${view.id}.png`} width={1192} unoptimized /></div><figcaption>{view.record}<span>Real interface · synthetic demo data · partial view</span></figcaption></figure>
      </div>
    </div>
  );
}
