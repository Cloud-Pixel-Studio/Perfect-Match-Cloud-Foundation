import {
  Boxes,
  CircleCheck,
  FileCheck2,
  Gauge,
  LockKeyhole,
  Network,
  ShieldCheck,
} from "lucide-react";
import Image from "next/image";

import { RuntimeStatus } from "../components/runtime-status";
import { ThemeToggle } from "../components/theme-toggle";

const foundations = [
  { label: "SaaS architecture", detail: "Tenant-aware boundaries", icon: Network },
  { label: "Auditability", detail: "Evidence-first governance", icon: FileCheck2 },
  { label: "Security gates", detail: "Local and reviewable", icon: ShieldCheck },
  { label: "Storage portability", detail: "S3-compatible interface", icon: Boxes },
];

export default function Home() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <Image alt="" height={36} priority src="/brand-mark.png" width={36} />
          <div>
            <strong>PERFECT MATCH</strong>
            <span>Quality Management Cloud</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          <a aria-current="page" className="nav-item active" href="#overview">
            <Gauge aria-hidden="true" size={18} />
            Overview
          </a>
          <a className="nav-item" href="#controls">
            <LockKeyhole aria-hidden="true" size={18} />
            Controls
          </a>
        </nav>
        <div className="sidebar-foot">
          <span className="foundation-tag">PMC-00</span>
          <span>Development foundation</span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="context-label">Perfect Match Cloud</span>
            <span className="context-separator" aria-hidden="true">/</span>
            <strong>Foundation</strong>
          </div>
          <ThemeToggle />
        </header>

        <main id="overview">
          <section className="intro-band">
            <div>
              <p className="eyebrow">Development foundation</p>
              <h1>Quality systems, built with clarity.</h1>
              <p className="intro-copy">
                The secure local platform baseline for the independent Perfect Match Cloud product.
              </p>
            </div>
            <div className="release-mark">
              <CircleCheck aria-hidden="true" size={19} />
              <div>
                <span>Foundation release</span>
                <strong>0.1.0</strong>
              </div>
            </div>
          </section>

          <RuntimeStatus />

          <section className="controls-section" id="controls" aria-labelledby="controls-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Architecture controls</p>
                <h2 id="controls-heading">Foundation invariants</h2>
              </div>
            </div>
            <div className="foundation-grid">
              {foundations.map(({ label, detail, icon: Icon }) => (
                <article className="foundation-item" key={label}>
                  <Icon aria-hidden="true" size={20} strokeWidth={1.8} />
                  <h3>{label}</h3>
                  <p>{detail}</p>
                </article>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
