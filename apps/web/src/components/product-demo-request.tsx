"use client";

import { Download, Mail } from "lucide-react";
import { useId, useState } from "react";

import {
  buildProductEnquiry,
  DEMO_CONTACT_EMAIL,
  isoInterestOptions,
  productPriorities,
  type ISOInterest,
  type ProductPriority,
} from "../lib/product-enquiry";

export function ProductDemoRequest() {
  const id = useId();
  const [company, setCompany] = useState("");
  const [seats, setSeats] = useState("25");
  const [priority, setPriority] = useState<ProductPriority>("general-qms");
  const [isoInterests, setISOInterests] = useState<ISOInterest[]>([]);
  const result = buildProductEnquiry({ company, seats, priority, isoInterests });
  const errors = result.ok ? {} : result.errors;

  function updateISOInterest(value: ISOInterest, checked: boolean) {
    setISOInterests((current) => checked ? [...current, value] : current.filter((item) => item !== value));
  }

  function downloadBrief() {
    if (!result.ok) return;
    const url = URL.createObjectURL(new Blob([result.brief], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "perfect-match-qms-demo-brief.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <form className="market-enquiry-form" onSubmit={(event) => event.preventDefault()}>
      <div className="market-enquiry-field">
        <label htmlFor={`${id}-company`}>Company <span>(optional)</span></label>
        <input
          autoComplete="organization"
          id={`${id}-company`}
          maxLength={120}
          onChange={(event) => setCompany(event.target.value)}
          value={company}
          aria-invalid={Boolean(errors.company)}
          aria-describedby={errors.company ? `${id}-company-error` : undefined}
        />
        {errors.company && <span className="market-enquiry-error" id={`${id}-company-error`} role="alert">{errors.company}</span>}
      </div>
      <div className="market-enquiry-field">
        <label htmlFor={`${id}-seats`}>Team seats</label>
        <input
          id={`${id}-seats`}
          inputMode="numeric"
          max={10_000}
          min={1}
          onChange={(event) => setSeats(event.target.value)}
          required
          step={1}
          type="number"
          value={seats}
          aria-invalid={Boolean(errors.seats)}
          aria-describedby={`${id}-seats-note${errors.seats ? ` ${id}-seats-error` : ""}`}
        />
        <small className="market-enquiry-note" id={`${id}-seats-note`}>A planning estimate, not a seat purchase.</small>
        {errors.seats && <span className="market-enquiry-error" id={`${id}-seats-error`} role="alert">{errors.seats}</span>}
      </div>
      <div className="market-enquiry-field">
        <label htmlFor={`${id}-priority`}>Main priority</label>
        <select id={`${id}-priority`} onChange={(event) => setPriority(event.target.value as ProductPriority)} value={priority}>
          {productPriorities.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>
      <fieldset className="market-enquiry-options" aria-describedby={`${id}-iso-note`}>
        <legend>ISO interests <span>(optional)</span></legend>
        {isoInterestOptions.map((option) => (
          <label key={option.value}>
            <input checked={isoInterests.includes(option.value)} onChange={(event) => updateISOInterest(option.value, event.target.checked)} type="checkbox" />
            <span>{option.label} <small>{option.state}</small></span>
          </label>
        ))}
        <small className="market-enquiry-note" id={`${id}-iso-note`}>Selections express interest. ISO addons are not available for purchase here.</small>
      </fieldset>
      <div className="market-enquiry-summary" aria-live="polite">
        <h3>Your demo brief</h3>
        <dl>
          <div><dt>Company workspace</dt><dd>1 independent workspace</dd></div>
          <div><dt>Team seats</dt><dd>{result.ok ? result.seats : "Enter a valid seat count"}</dd></div>
          <div><dt>ISO interests</dt><dd>{isoInterestOptions.filter((option) => isoInterests.includes(option.value)).map((option) => option.label).join(", ") || "None selected"}</dd></div>
        </dl>
        <p className="market-enquiry-note">This is a demo brief, not a price quote, order or subscription.</p>
      </div>
      <div className="market-enquiry-actions">
        <a aria-disabled={!result.ok} href={result.ok ? result.mailto : undefined} role="link" tabIndex={result.ok ? undefined : -1}><Mail aria-hidden="true" size={17} />Prepare demo email</a>
        <button disabled={!result.ok} onClick={downloadBrief} type="button"><Download aria-hidden="true" size={17} />Download brief</button>
      </div>
      <p className="market-enquiry-note">The email button opens your mail app. Nothing is sent until you review and send the email. You can also write to <a href={`mailto:${DEMO_CONTACT_EMAIL}`}>{DEMO_CONTACT_EMAIL}</a>.</p>
      <p className="market-enquiry-note">No personal details are required. Your choices stay on this page until you open your mail app or download a local brief.</p>
    </form>
  );
}
