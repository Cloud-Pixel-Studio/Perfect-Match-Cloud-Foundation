import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { connection } from "next/server";
import { ArrowDown, ArrowRight, Building2, Check, CheckCircle2, ClipboardCheck, FileCheck2, Layers3, LockKeyhole, Mail, ShieldCheck, UsersRound } from "lucide-react";

import { BrandMark } from "../../components/brand-mark";
import { ThemeToggle } from "../../components/theme-toggle";
import { ProductTour } from "../../components/product-tour";
import { ProductDemoRequest } from "../../components/product-demo-request";
import "./products.css";

export const metadata: Metadata = {
  title: "Quality management software for connected teams",
  description: "Connect documents, risks and corrective actions in your company's own quality workspace. Explore Perfect Match QMS and request a product demonstration.",
};

const capabilities = ["Processes & ownership", "Controlled documents", "Controls & evidence", "Risks & opportunities", "Nonconformities", "Corrective actions", "Workflows & approvals", "Action center & audit history"];
const audiences = [
  { icon: FileCheck2, role: "FOR QUALITY LEADERS", question: "Which revision is the right one?", copy: "Keep document revisions, independent reviews and release decisions together.", detail: "Document control · review history · private files" },
  { icon: ClipboardCheck, role: "FOR PROCESS OWNERS", question: "What needs my attention next?", copy: "Follow assigned actions, responsibilities and due dates within your organization scope.", detail: "Action center · process scope · corrective actions" },
  { icon: ShieldCheck, role: "FOR IT & ASSURANCE", question: "Who can see, change or approve it?", copy: "Keep company boundaries and QMS authority explicit, with recorded changes to inspect.", detail: "Tenant isolation · scoped capabilities · audit history" },
];
const standards = [
  { code: "ISO 9001", title: "Quality management", state: "In preparation", detail: "Discuss the standard and edition relevant to your quality system." },
  { code: "ISO 14001", title: "Environmental management", state: "Planned", detail: "Register interest in a future environmental management addon." },
  { code: "ISO 45001", title: "Occupational health & safety", state: "Planned", detail: "Register interest in a future OH&S management addon." },
];
const questions = [
  ["Does each company have its own independent space?", "Yes. The tenant is your company's separate workspace for its people, configuration and records. Access is restricted to the organization and scope assigned to each person."],
  ["What belongs to the core QMS?", "The QMS is one core product, rather than separately sold operational modules. The current product preview includes processes, document control, controls and evidence, risks, nonconformities, corrective actions, workflows and the Action Center. Additional capabilities continue to be developed."],
  ["Is a seat the same as approval authority?", "No. Seats describe team capacity. QMS responsibilities determine what a person may read, change, review or approve within a defined organization scope."],
  ["Which ISO addons can we discuss?", "ISO 9001 is in preparation. ISO 14001 and ISO 45001 are planned. Each future addon will identify its standard and edition. Availability, content licensing and commercial terms must be confirmed before contracting."],
  ["Does using the platform certify our company?", "No. Software can support controlled work and evidence, but it does not grant ISO certification. ISO/IEC 27001 and NIST are security objectives for the platform, not certifications claimed by this website."],
  ["Can we purchase or start a free trial here?", "Commercial rollout and pricing are still in preparation. The product tour shows the current foundation. Request a demo to discuss your processes, team size, standards and availability; no purchase or automatic trial is created."],
];

export default async function ProductsPage() {
  await connection();
  return (
    <div className="market-page">
      <a className="skip-link" href="#market-main">Skip to product content</a>
      <header className="market-header">
        <Link className="market-brand" href="/"><BrandMark priority /><span><strong>PERFECT MATCH QMS</strong><small>Quality Operations Cloud</small></span></Link>
        <nav className="market-navigation" aria-label="Product navigation"><a href="#product-tour">Product tour</a><a href="#teams">For your team</a><a href="#platform">The platform</a><a href="#standards">ISO addons</a><a href="#security">Security</a></nav>
        <div className="market-header-actions"><ThemeToggle /><Link className="market-signin" href="/">Log in</Link><a className="market-button market-button-small" href="#demo">Request a demo <ArrowRight aria-hidden="true" size={15} /></a></div>
      </header>

      <main id="market-main">
        <section className="market-hero market-container" aria-labelledby="product-heading">
          <p className="market-eyebrow"><span /> QUALITY MANAGEMENT, CONNECTED</p>
          <h1 id="product-heading">Bring quality into focus. <br /><em>Keep the evidence connected.</em></h1>
          <p className="market-lead">Documents, risks and corrective actions in one private workspace for your company. Give your team a clear place to act, review and improve.</p>
          <div className="market-hero-actions"><a className="market-button" href="#product-tour">Explore the product <ArrowDown aria-hidden="true" size={18} /></a><a className="market-button market-button-secondary" href="#demo">Request a demo <ArrowRight aria-hidden="true" size={18} /></a></div>
          <p className="market-availability"><span />Product preview · Commercial rollout in preparation</p>
          <figure className="market-product-window">
            <div className="market-window-bar"><span><i /><i /><i /></span><small>Perfect Match QMS / Your company workspace</small><LockKeyhole aria-hidden="true" size={14} /></div>
            <div className="market-hero-screen"><Image alt="Real Perfect Match QMS workspace showing priorities and modules with synthetic demonstration data" height={1000} src="/brand/product/overview.png" width={1440} priority unoptimized /></div>
            <figcaption><span><CheckCircle2 aria-hidden="true" size={15} />Real product interface</span><span>Synthetic demo data · illustrative counts</span><a href="#product-tour">See what is behind the screen <ArrowRight aria-hidden="true" size={14} /></a></figcaption>
          </figure>
        </section>

        <section className="market-proof-strip market-container" aria-label="Product principles"><span><Building2 aria-hidden="true" size={21} /><strong>Your company. Its own space.</strong></span><span><UsersRound aria-hidden="true" size={21} /><strong>Clear responsibilities for every seat.</strong></span><span><Layers3 aria-hidden="true" size={21} /><strong>One QMS. Standards added by edition.</strong></span></section>

        <section className="market-section market-container" id="product-tour" aria-labelledby="tour-heading"><div className="market-section-heading"><div><p className="market-eyebrow">A CLOSER LOOK</p><h2 id="tour-heading">See the work.<br />Follow the evidence.</h2></div><p>Explore three everyday quality workflows in the current product. Each view is a real capture from our synthetic demonstration environment.</p></div><ProductTour /></section>

        <section className="market-audiences" id="teams" aria-labelledby="teams-heading"><div className="market-container"><div className="market-section-heading"><div><p className="market-eyebrow">DIFFERENT RESPONSIBILITIES. ONE SYSTEM.</p><h2 id="teams-heading">Built around the questions<br />your team actually asks.</h2></div></div><div className="market-audience-grid">{audiences.map(({ icon: Icon, role, question, copy, detail }) => <article key={role}><Icon aria-hidden="true" size={25} /><p className="market-eyebrow">{role}</p><h3>{question}</h3><p>{copy}</p><small>{detail}</small></article>)}</div></div></section>

        <section className="market-section market-container" id="platform" aria-labelledby="platform-heading"><div className="market-section-heading"><div><p className="market-eyebrow">A SIMPLE PRODUCT MODEL</p><h2 id="platform-heading">One company workspace.<br />A QMS that works together.</h2></div><p>Start the conversation with your company, your team and the standards you need. Operational QMS areas belong to the same core product.</p></div><div className="market-offer-grid"><article className="market-core-offer"><span className="market-offer-label">01 / THE CORE PRODUCT</span><h3>Perfect Match QMS</h3><p>A connected foundation for quality work, with responsibilities and evidence in context.</p><ul>{capabilities.map((capability) => <li key={capability}><Check aria-hidden="true" size={16} />{capability}</li>)}</ul><small>Current foundation shown in the product tour. Further capabilities remain in development.</small></article><div className="market-offer-options"><article><span className="market-offer-label">02 / YOUR TEAM</span><UsersRound aria-hidden="true" size={24} /><h3>Seats inside your company space</h3><p>Define the team capacity your organization needs. Access and approval responsibilities stay separately assigned.</p></article><article><span className="market-offer-label">03 / YOUR STANDARDS</span><Layers3 aria-hidden="true" size={24} /><h3>ISO addons by standard and edition</h3><p>Extend the core QMS with relevant standards as they become available. No separate purchase for each operational module.</p></article></div></div></section>

        <section className="market-standards market-container" id="standards" aria-labelledby="standards-heading"><div className="market-section-heading"><div><p className="market-eyebrow">PLAN YOUR STANDARDS</p><h2 id="standards-heading">The standards you need.<br />An edition you can identify.</h2></div><p>Tell us which standards matter to your organization. These are the current development stages, not a list of released certifications.</p></div><div className="market-standard-grid">{standards.map((standard) => <article key={standard.code}><span className={`market-standard-state ${standard.state === "Planned" ? "is-planned" : ""}`}>{standard.state}</span><p>{standard.code}</p><h3>{standard.title}</h3><p>{standard.detail}</p><a href="#demo">Discuss your scope <ArrowRight aria-hidden="true" size={16} /></a></article>)}</div><p className="market-quiet-note">Addon availability, content licensing, editions and commercial terms will be confirmed before contracting.</p></section>

        <section className="market-security market-container" id="security" aria-labelledby="security-heading"><div><span className="market-security-mark"><ShieldCheck aria-hidden="true" size={30} /></span><p className="market-eyebrow">CONTROL IS PART OF THE PRODUCT</p><h2 id="security-heading">Your quality data.<br />Clear boundaries.</h2><p>Ask how records are scoped, who can approve a change and how the history is preserved. The foundation already includes controls you can inspect in a demonstration.</p><a href="#demo">Include security in your demo <ArrowRight aria-hidden="true" size={16} /></a></div><ul><li><LockKeyhole aria-hidden="true" size={22} /><span><strong>Company-level separation</strong>Tenant isolation and explicitly scoped QMS capabilities.</span></li><li><FileCheck2 aria-hidden="true" size={22} /><span><strong>Controlled evidence</strong>Private file storage, malware scanning and revision history.</span></li><li><ClipboardCheck aria-hidden="true" size={22} /><span><strong>Decisions with a history</strong>Independent review controls and recorded changes.</span></li></ul><p className="market-security-note">ISO/IEC 27001 and NIST guide security objectives. No certification or production-readiness claim is made.</p></section>

        <section className="market-section market-container market-faq" aria-labelledby="faq-heading"><div><p className="market-eyebrow">BEFORE WE TALK</p><h2 id="faq-heading">Good questions.<br />Clear answers.</h2><p>Understand the product model and current availability before planning your next step.</p></div><div>{questions.map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>

        <section className="market-demo-section" id="demo" aria-labelledby="demo-heading"><div className="market-container market-demo-grid"><div><p className="market-eyebrow">LET’S LOOK AT YOUR QUALITY WORK</p><h2 id="demo-heading">Bring your questions.<br /><em>We’ll bring the product.</em></h2><p>Plan a focused demonstration around the work your company needs to control.</p><ol><li><span>01</span>Choose your team size and main priority.</li><li><span>02</span>Tell us which standards you want to discuss.</li><li><span>03</span>Review and send the prepared email.</li></ol><a className="market-demo-email" href="mailto:Demo@invperfectmatch.com"><Mail aria-hidden="true" size={17} />Demo@invperfectmatch.com</a><small>Product preview. Pricing and commercial rollout are in preparation.</small></div><ProductDemoRequest /></div></section>
      </main>

      <footer className="market-footer market-container"><div><BrandMark /><span><strong>PERFECT MATCH QMS</strong><small>Quality work. Connected evidence.</small></span></div><nav aria-label="Product resources"><a href="#product-tour">Product tour</a><Link href="/design-studio">Explore the visual library</Link><a href="mailto:Demo@invperfectmatch.com">Contact</a><Link href="/">Client login</Link></nav><p>Independent QMS platform · Company workspaces · Seats · ISO editions</p></footer>
    </div>
  );
}
