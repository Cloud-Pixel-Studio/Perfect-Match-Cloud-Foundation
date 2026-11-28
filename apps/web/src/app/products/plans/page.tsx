import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { ArrowLeft, ArrowRight, Building2 } from "lucide-react";

import { ProductHeader } from "../../../components/product-header";
import { companyStoragePlans, formatStorageCapacity, storageTerms } from "../../../lib/company-storage-plans";
import "../products.css";

export const metadata: Metadata = {
  title: "Company plans and included storage",
  description: "Compare proposed storage allowances for Perfect Match QMS and see what a company agreement will cover.",
};

export default async function CompanyPlansPage() {
  await connection();
  return (
    <div className="market-page">
      <a className="skip-link" href="#plans-main">Skip to company plans</a>
      <ProductHeader plansPage />
      <main id="plans-main" className="market-container market-plans">
        <nav aria-label="Breadcrumb">
          <Link className="market-plans-back" href="/products"><ArrowLeft aria-hidden="true" size={17} /> Product overview</Link>
        </nav>
        <header className="market-plans-heading">
          <span className="market-plans-icon"><Building2 aria-hidden="true" size={24} /></span>
          <h1>Plans &amp; included storage</h1>
          <p>Every plan includes the core QMS and a storage allowance for one company. Your agreement will state the capacity, seats, ISO editions and recurring price.</p>
        </header>
        <section aria-labelledby="capacity-heading">
          <h2 id="capacity-heading">Proposed capacity per company</h2>
          <ul className="market-plan-grid" role="list">
            {companyStoragePlans.map(plan => (
              <li key={plan.id}>
                <h3>{plan.name}</h3>
                <p className="market-plan-capacity">{formatStorageCapacity(plan.capacityMb)}</p>
                <p>{plan.use}</p>
                <p className="market-plan-scope">{plan.scope}</p>
                <Link className="market-button market-button-secondary market-button-small" href={`/products?plan=${plan.id}#demo`}>
                  Discuss {plan.name} <ArrowRight aria-hidden="true" size={16} />
                </Link>
              </li>
            ))}
          </ul>
          <p className="market-quiet-note">Plans and capacities are proposed for discussion. Final terms will appear in your signed agreement.</p>
        </section>
        <section className="market-plan-terms" aria-labelledby="storage-terms-heading">
          <h2 id="storage-terms-heading">How the allowance works</h2>
          <dl>
            <div><dt>What counts</dt><dd>{storageTerms.counted} The allowance measures space occupied, including older versions kept for retention.</dd></div>
            <div><dt>Included backups</dt><dd>{storageTerms.excluded} Managed backups are covered by the recurring price.</dd></div>
            <div><dt>When space runs low</dt><dd>Proposed alerts at {storageTerms.alerts[0]}% and {storageTerms.alerts[1]}%. {storageTerms.full}</dd></div>
            <div><dt>Adding storage</dt><dd>Proposed expansion in blocks of {formatStorageCapacity(storageTerms.expansionMb)}. {storageTerms.expansion}</dd></div>
          </dl>
          <p className="market-quiet-note">Each workspace has its own allowance. One MB is 1,000,000 bytes.</p>
        </section>
      </main>
    </div>
  );
}
