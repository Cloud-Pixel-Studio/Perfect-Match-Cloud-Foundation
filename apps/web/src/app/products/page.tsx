import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { connection } from "next/server";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenCheck,
  Building2,
  Check,
  CheckCircle2,
  ClipboardCheck,
  FileCheck2,
  Gauge,
  Layers3,
  ListChecks,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";

import { ThemeToggle } from "../../components/theme-toggle";
import { BrandMark } from "../../components/brand-mark";

export const metadata: Metadata = {
  title: "Products",
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

const productPillars = [
  { icon: Gauge, title: "One operating view", copy: "Priorities, records and governed work stay connected." },
  { icon: LockKeyhole, title: "A private company space", copy: "Every tenant keeps its own people, configuration and records." },
  { icon: ClipboardCheck, title: "Evidence in context", copy: "Approvals and improvement work retain their traceability." },
  { icon: Sparkles, title: "Standards when needed", copy: "Activate only the ISO editions included in the contract." },
];

export default async function ProductsPage() {
  // Per-request rendering lets the CSP middleware attach its nonce to the
  // client-side theme control instead of serving a stale build-time nonce.
  await connection();
  return (
    <div className="product-page">
      <header className="product-header">
        <Link className="product-brand" href="/">
          <BrandMark priority />
          <span className="product-brand-name"><strong>PERFECT MATCH QMS</strong><small>Quality Operations Cloud</small></span>
          <span className="sr-only">Home</span>
        </Link>
        <nav aria-label="Product navigation">
          <a href="#platform">Platform</a><a href="#standards">ISO addons</a><a href="#security">Security</a><Link href="/design-studio">Design studio</Link>
          <ThemeToggle />
          <Link className="product-login" href="/">Open workspace <ArrowRight aria-hidden="true" size={16} /></Link>
        </nav>
      </header>

      <main className="product-main">
        <section className="product-hero" aria-labelledby="product-heading">
          <div className="product-hero-copy">
            <p className="eyebrow"><span /> One controlled quality system</p>
            <h1 id="product-heading">Your QMS foundation.<br /><em>Standards added by edition.</em></h1>
            <p>Perfect Match QMS gives each company its own governed workspace, the seats its team needs and the ISO addons included in its contract.</p>
            <div className="product-hero-actions">
              <a className="primary-action" href="#platform">Explore the platform <ArrowRight aria-hidden="true" size={17} /></a>
              <Link className="secondary-action compact-action" href="/">Open secure workspace</Link>
            </div>
            <div className="product-hero-trust" aria-label="Product principles">
              <span><CheckCircle2 aria-hidden="true" size={16} />Private tenant workspace</span>
              <span><CheckCircle2 aria-hidden="true" size={16} />Explicit QMS authority</span>
              <span><CheckCircle2 aria-hidden="true" size={16} />Controlled audit history</span>
            </div>
          </div>

          <div className="product-showcase" aria-label="Illustrative Perfect Match workspace preview">
            <div className="showcase-window-bar"><span /><span /><span /><small>Perfect Match QMS · Tenant workspace</small></div>
            <div className="showcase-layout">
              <aside aria-hidden="true">
                <div className="showcase-brand"><BrandMark size={26} /><span /></div>
                <span className="showcase-nav active" /><span className="showcase-nav" /><span className="showcase-nav" /><span className="showcase-nav short" />
              </aside>
              <div className="showcase-content">
                <header><div><small>Quality workspace</small><strong>Good morning</strong></div><span className="showcase-avatar">PM</span></header>
                <div className="showcase-banner"><span><small>Current tenant</small><strong>Your company</strong></span><ShieldCheck aria-hidden="true" size={24} /></div>
                <div className="showcase-metrics">
                  <article><small>Assigned actions</small><strong>08</strong><span>3 due soon</span></article>
                  <article><small>Documents</small><strong>24</strong><span>2 in review</span></article>
                  <article><small>Open CAPA</small><strong>04</strong><span>1 verification</span></article>
                </div>
                <div className="showcase-work"><div><small>Priority work</small><strong>Corrective action review</strong></div><span>Open record <ArrowRight aria-hidden="true" size={13} /></span></div>
              </div>
            </div>
            <span className="product-preview-label">Illustrative product preview</span>
          </div>
        </section>

        <section className="product-principles" aria-label="Commercial model">
          <span><Building2 aria-hidden="true" size={19} /><span><strong>One tenant</strong><small>A private company workspace</small></span></span>
          <span><UsersRound aria-hidden="true" size={19} /><span><strong>Flexible seats</strong><small>Capacity for active members</small></span></span>
          <span><BookOpenCheck aria-hidden="true" size={19} /><span><strong>ISO addons</strong><small>Contracted standard and edition</small></span></span>
        </section>

        <figure className="product-brand-art">
          <Image alt="Abstract document and evidence pathways converging into one governed quality system" height={941} src="/brand/hero-quality-network.png" width={1672} />
          <figcaption><strong>Aligned Evidence</strong><span>Requirements, responsibility and proof converge in one controlled workspace.</span></figcaption>
        </figure>

        <section className="product-story" aria-labelledby="product-story-heading">
          <div className="product-story-heading"><p className="eyebrow">What the platform brings together</p><h2 id="product-story-heading">Quality work feels clearer when everything has a place.</h2></div>
          <div className="product-pillar-grid">{productPillars.map(({ icon: Icon, title, copy }, index) => <article key={title}><span className="product-pillar-number">0{index + 1}</span><Icon aria-hidden="true" size={22} /><h3>{title}</h3><p>{copy}</p></article>)}</div>
        </section>

        <section className="product-section product-platform-section" id="platform" aria-labelledby="platform-heading">
          <div className="product-section-heading">
            <div><p className="eyebrow">Core product</p><h2 id="platform-heading">Perfect Match QMS</h2><p>The operational foundation every tenant receives. Standards extend this system; they do not fragment it into separate applications.</p></div>
            <span className="product-state ready"><BadgeCheck aria-hidden="true" size={15} /> QMS foundation</span>
          </div>
          <div className="product-core-grid">
            <div className="product-core-copy">
              <h3>Complete quality operations—not a bundle of disconnected modules.</h3>
              <p>Processes, records, evidence and improvement work stay connected within the same governed organization structure.</p>
              <div className="product-operating-flow" aria-label="Quality operating flow"><span><Layers3 aria-hidden="true" size={18} />Define</span><ArrowRight aria-hidden="true" size={16} /><span><ListChecks aria-hidden="true" size={18} />Operate</span><ArrowRight aria-hidden="true" size={16} /><span><FileCheck2 aria-hidden="true" size={18} />Prove</span></div>
              <p className="product-note"><ShieldCheck aria-hidden="true" size={17} />A purchased seat or platform role never grants approval authority by itself. Responsibilities remain explicit and scoped.</p>
            </div>
            <ul className="product-capabilities">{qmsCapabilities.map((capability) => <li key={capability}><Check aria-hidden="true" size={16} />{capability}</li>)}</ul>
          </div>
        </section>

        <section className="product-section product-seats" aria-labelledby="seats-heading">
          <div><p className="eyebrow">Capacity with control</p><h2 id="seats-heading">Seats inside each tenant. Authority belongs to the process.</h2><p>Seats determine how many active members a tenant can maintain. QMS permissions stay separate, auditable and limited to the assigned organization scope.</p></div>
          <div className="seat-model" aria-label="Seat model"><span><small>01</small>Tenant subscription</span><ArrowRight aria-hidden="true" size={17} /><span><small>02</small>Purchased seats</span><ArrowRight aria-hidden="true" size={17} /><span><small>03</small>Scoped responsibilities</span></div>
        </section>

        <section className="product-section" id="standards" aria-labelledby="standards-heading">
          <div className="product-section-heading"><div><p className="eyebrow">Commercial addons</p><h2 id="standards-heading">ISO standards by controlled edition</h2><p>Each addon identifies its standard, edition, entitlement and lifecycle. Standards content will only be offered when licensing and product validation are complete.</p></div></div>
          <div className="standard-grid">{standards.map((standard, index) => <article className="standard-card" key={standard.code}><div className="standard-card-top"><span className="standard-card-number">0{index + 1}</span><span className={`product-state ${standard.state === "In preparation" ? "preparing" : "planned"}`}>{standard.state}</span></div><p>{standard.code}</p><h3>{standard.name}</h3><p>{standard.copy}</p><dl><div><dt>Product type</dt><dd>QMS addon</dd></div><div><dt>Entitlement</dt><dd>Tenant + edition</dd></div></dl></article>)}</div>
          <p className="catalog-disclaimer">Availability and pricing are intentionally not shown until commercial terms, content licensing and release evidence are approved.</p>
        </section>

        <section className="product-security" id="security" aria-labelledby="security-heading">
          <div><span className="security-icon"><ShieldCheck aria-hidden="true" size={26} /></span><p className="eyebrow">Security by design</p><h2 id="security-heading">Built for controlled, evidence-based operation.</h2><p>The architecture uses tenant isolation, explicit capabilities, append-only audit history, private object storage, malware scanning and controlled identity sessions.</p></div>
          <ul><li><Check aria-hidden="true" size={16} /><span><strong>Security objectives</strong>ISO/IEC 27001 and NIST requirements are mapped as objectives.</span></li><li><Check aria-hidden="true" size={16} /><span><strong>Evidence before claims</strong>No certification or production readiness is claimed without verified evidence.</span></li><li><Check aria-hidden="true" size={16} /><span><strong>Separated boundaries</strong>Seats, roles and QMS authority remain independent controls.</span></li></ul>
        </section>
      </main>

      <footer className="product-footer"><span>Perfect Match QMS</span><Link className="product-library-link" href="/design-studio">Explore the visual library <ArrowRight aria-hidden="true" size={16} /></Link><span>Complete QMS · tenant seats · edition-controlled ISO addons</span></footer>
    </div>
  );
}
