"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import {
  companyStoragePlans, formatStorageCapacity, matchCompanyStoragePlan, parseStorageMb,
} from "../lib/company-storage-plans";
import { parseRequestedSeats } from "../lib/product-enquiry";

export function CompanyPlanGuide() {
  const id = useId();
  const [estimate, setEstimate] = useState<{ seats: number; storageMb: number } | null>(null);
  const [issue, setIssue] = useState("");
  const fit = estimate ? matchCompanyStoragePlan(estimate.storageMb) : undefined;
  const plan = fit ?? companyStoragePlans[companyStoragePlans.length - 1];
  const extraSeats = estimate && plan.includedSeats !== null ? Math.max(0, estimate.seats - plan.includedSeats) : 0;

  function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const inputs = new FormData(event.currentTarget);
    const seats = parseRequestedSeats(inputs.get("seats"));
    const storageMb = parseStorageMb(inputs.get("storage"));
    if (seats === undefined || storageMb === undefined) {
      setEstimate(null);
      setIssue(seats === undefined ? "Enter a whole number of seats from 1 to 10,000." : "Enter a whole number of megabytes, starting at zero.");
      return;
    }
    setIssue("");
    setEstimate({ seats, storageMb });
  }

  return <section className="market-plan-terms market-plan-guide" aria-labelledby={`${id}-heading`}>
    <div>
      <h2 id={`${id}-heading`}>Find a plan for your company</h2>
      <p>Enter your team size and estimated storage. We’ll show the smallest proposed storage allowance that fits. Seats and ISO editions are confirmed with your quote.</p>
    </div>
    <form className="market-plan-guide-form" onSubmit={compare}
      onChange={() => { setEstimate(null); setIssue(""); }}>
      <div className="market-enquiry-field">
        <label htmlFor={`${id}-seats`}>People who need access</label>
        <input id={`${id}-seats`} name="seats" type="number" inputMode="numeric" min={1} max={10_000} step={1}
          defaultValue={companyStoragePlans[0].includedSeats} required />
      </div>
      <div className="market-enquiry-field">
        <label htmlFor={`${id}-storage`}>Estimated retained files (MB)</label>
        <input id={`${id}-storage`} name="storage" type="number" inputMode="numeric" min={0} step={1}
          aria-describedby={`${id}-units`} required />
        <small className="market-enquiry-note" id={`${id}-units`}>1 GB is 1,000 MB. Include older revisions you need to keep.</small>
      </div>
      <button className="market-button market-button-small" type="submit">Compare my needs</button>
    </form>
    {issue && <p role="alert" className="market-enquiry-error">{issue}</p>}
    <div aria-live="polite">
      {estimate && <div className="market-plan-result">
        <div>
          <h3>{fit ? `${plan.name} fits your storage estimate` : "You need a custom storage quote"}</h3>
          <p>{fit
            ? `${formatStorageCapacity(estimate.storageMb)} estimated out of ${formatStorageCapacity(plan.capacityMb)} proposed for one company.`
            : `${formatStorageCapacity(estimate.storageMb)} estimated. The largest proposed allowance is ${formatStorageCapacity(plan.capacityMb)}.`}</p>
          <p>{plan.includedSeats === null
            ? `Ask for ${estimate.seats} seats in your quote.`
            : extraSeats
              ? `Basic includes ${plan.includedSeats} seats. Your quote would need ${extraSeats} additional ${extraSeats === 1 ? "seat" : "seats"}.`
              : `Basic covers your request for ${estimate.seats} of its ${plan.includedSeats} included seats.`}</p>
        </div>
        <Link className="market-button market-button-secondary market-button-small"
          href={`/products?${new URLSearchParams({ plan: plan.id, seats: String(estimate.seats), storageMb: String(estimate.storageMb) })}#demo`}>
          Continue to demo brief <ArrowRight aria-hidden="true" size={16} />
        </Link>
      </div>}
    </div>
  </section>;
}
