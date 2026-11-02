import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { connection } from "next/server";
import { ArrowRight, BadgeCheck, BookOpenCheck, Building2, Check, FileLock2, Layers3, ShieldCheck, UsersRound } from "lucide-react";
import { ThemeToggle } from "../../components/theme-toggle";

export const metadata: Metadata = {
  title: "Products | Perfect Match QMS",
  description: "Perfect Match QMS platform, tenant seats and edition-controlled ISO addons.",
};

const qmsCapabilities = [
  "Processes and organization scope",
  "Controlled documents and revisions",
  "Controls, implementations and evidence",
  "Risks and opportunities",
  "Nonconformities and containment",
  "Corrective and preventive actions",
  "Controlled workflows and approvals",
  "Audit history and explicit responsibilities",
];

const standards = [
  { code: "ISO 9001", name: "Quality management", state: "In preparation", copy: "Edition-controlled guidance and mappings for the quality management system." },
  { code: "ISO 14001", name: "Environmental management", state: "Planned", copy: "A future addon for environmental obligations, aspects and operational controls." },
  { code: "ISO 45001", name: "Occupational health & safety", state: "Planned", copy: "A future addon for hazards, OH&S controls and worker participation." },
];

export default async function ProductsPage() {
  // Per-request rendering lets the CSP middleware attach its nonce to the
  // client-side theme control instead of serving a stale build-time nonce.
  await connection();
  return <div className="product-page">
    <header className="product-header">
      <Link className="product-brand" href="/"><Image alt="" height={40} priority src="/brand-mark.png" unoptimized width={40} /><span className="product-brand-name"><strong>PERFECT MATCH</strong><small>Quality Management Cloud</small></span><span className="sr-only">Home</span></Link>
      <nav aria-label="Product navigation"><a href="#platform">Platform</a><a href="#standards">ISO addons</a><a href="#security">Security</a><ThemeToggle /><Link className="product-login" href="/">Open workspace <ArrowRight aria-hidden="true" size={16} /></Link></nav>
    </header>

    <main className="product-main">
      <section className="product-hero" aria-labelledby="product-heading">
        <div><p className="eyebrow">One controlled quality system</p><h1 id="product-heading">Your QMS foundation.<br />Standards added by edition.</h1><p>Perfect Match QMS is the complete product. Each company operates in its own tenant, adds the seats it needs, and activates only the ISO addons it contracts.</p><div className="product-hero-actions"><a className="primary-action" href="#platform">Explore the platform <ArrowRight aria-hidden="true" size={17} /></a><Link className="secondary-action compact-action" href="/">Open secure workspace</Link></div></div>
        <aside className="product-assurance" aria-label="Product model"><span><Building2 aria-hidden="true" size={20} /><span><strong>Tenant</strong><small>One isolated company context</small></span></span><span><UsersRound aria-hidden="true" size={20} /><span><strong>Seats</strong><small>Capacity for active members</small></span></span><span><BookOpenCheck aria-hidden="true" size={20} /><span><strong>ISO addons</strong><small>Contracted by standard and edition</small></span></span></aside>
      </section>

      <section className="product-principles" aria-label="Platform principles"><span><ShieldCheck aria-hidden="true" size={18} /> Explicit QMS authority</span><span><FileLock2 aria-hidden="true" size={18} /> Controlled records</span><span><Layers3 aria-hidden="true" size={18} /> Tenant-scoped data</span></section>

      <section className="product-section" id="platform" aria-labelledby="platform-heading">
        <div className="product-section-heading"><div><p className="eyebrow">Core product</p><h2 id="platform-heading">Perfect Match QMS</h2></div><span className="product-state ready"><BadgeCheck aria-hidden="true" size={15} /> Foundation</span></div>
        <div className="product-core-grid"><div className="product-core-copy"><h3>Complete quality operations—not a bundle of disconnected modules.</h3><p>The QMS foundation keeps processes, records, evidence and improvement work connected within the same governed organization structure.</p><p className="product-note"><ShieldCheck aria-hidden="true" size={17} /> A purchased seat or platform role never grants approval authority by itself. Responsibilities remain explicit and scoped.</p></div><ul className="product-capabilities">{qmsCapabilities.map((capability) => <li key={capability}><Check aria-hidden="true" size={16} />{capability}</li>)}</ul></div>
      </section>

      <section className="product-section product-seats" aria-labelledby="seats-heading">
        <div><p className="eyebrow">Capacity</p><h2 id="seats-heading">Seats inside each tenant</h2><p>Seats determine how many active members a company can maintain. QMS permissions remain separate, auditable and limited to the assigned organization scope.</p></div><div className="seat-model" aria-label="Seat model"><span>Tenant subscription</span><ArrowRight aria-hidden="true" size={17} /><span>Purchased seats</span><ArrowRight aria-hidden="true" size={17} /><span>Scoped responsibilities</span></div>
      </section>

      <section className="product-section" id="standards" aria-labelledby="standards-heading">
        <div className="product-section-heading"><div><p className="eyebrow">Commercial addons</p><h2 id="standards-heading">ISO standards by controlled edition</h2><p>Each addon will identify its standard, edition, entitlement and lifecycle. Standards content will only be offered when licensing and product validation are complete.</p></div></div>
        <div className="standard-grid">{standards.map((standard) => <article className="standard-card" key={standard.code}><span className={`product-state ${standard.state === "In preparation" ? "preparing" : "planned"}`}>{standard.state}</span><p>{standard.code}</p><h3>{standard.name}</h3><p>{standard.copy}</p><dl><div><dt>Product type</dt><dd>QMS addon</dd></div><div><dt>Entitlement</dt><dd>Tenant + edition</dd></div></dl></article>)}</div>
        <p className="catalog-disclaimer">Availability and pricing are intentionally not shown until commercial terms, content licensing and release evidence are approved.</p>
      </section>

      <section className="product-security" id="security" aria-labelledby="security-heading"><div><p className="eyebrow">Security by design</p><h2 id="security-heading">Built for controlled, evidence-based operation.</h2><p>The architecture uses tenant isolation, explicit capabilities, append-only audit history, private object storage, malware scanning and controlled identity sessions.</p></div><ul><li><Check aria-hidden="true" size={16} />ISO/IEC 27001 and NIST requirements are mapped as security objectives.</li><li><Check aria-hidden="true" size={16} />No certification or production readiness is claimed without verified evidence.</li><li><Check aria-hidden="true" size={16} />Seats, roles and QMS authority remain separate security boundaries.</li></ul></section>
    </main>

    <footer className="product-footer"><span>Perfect Match QMS</span><span>Complete QMS · tenant seats · edition-controlled ISO addons</span></footer>
  </div>;
}
