import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileCheck2,
  Layers3,
  ListChecks,
  ScanSearch,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { designAssetCatalog, type DesignAssetSpec } from "../../lib/design-studio";
import { BrandMark } from "../../components/brand-mark";
import { ThemeToggle } from "../../components/theme-toggle";

export const metadata: Metadata = {
  title: "AI Design Studio",
  description: "Controlled visual asset demonstration for Perfect Match QMS.",
};

type PageProps = { searchParams: Promise<{ asset?: string }> };

function AssetBrand({ inverse = false }: { inverse?: boolean }) {
  return (
    <div className={`studio-asset-brand ${inverse ? "inverse" : ""}`}>
      <Image
        alt=""
        aria-hidden="true"
        className="studio-asset-logo"
        height={58}
        src={inverse ? "/brand/selected/pmqms-mark-dark.svg" : "/brand/selected/pmqms-mark.svg"}
        unoptimized
        width={58}
      />
      <span><strong>PERFECT MATCH QMS</strong><small>Quality Operations Cloud</small></span>
    </div>
  );
}

function DesignCanvas({ asset, exportMode = false }: { asset: DesignAssetSpec; exportMode?: boolean }) {
  const common = {
    className: `studio-canvas studio-canvas-${asset.slug} studio-size-${asset.width}x${asset.height} ${exportMode ? "is-export" : ""}`,
    "data-export-asset": exportMode ? asset.slug : undefined,
  };

  if (asset.slug === "platform-hero") {
    return <article {...common}><div className="studio-asset-copy dark"><AssetBrand inverse /><p className="studio-kicker">CONTROLLED QUALITY OPERATIONS</p><h2>Work with clarity.<br /><em>Improve with evidence.</em></h2><p>Processes, records, actions and proof connected in one governed workspace.</p><span className="studio-asset-cta">Explore Perfect Match QMS</span></div><span className="studio-disclosure">Illustrative brand visual</span></article>;
  }
  if (asset.slug === "saas-product-overview") {
    return <article {...common}><div className="studio-product-copy"><AssetBrand /><p className="studio-kicker">ONE PRIVATE COMPANY SPACE</p><h2>Your quality system.<br /><em>One source of evidence.</em></h2><ul><li><ShieldCheck />Tenant-isolated workspace</li><li><ClipboardCheck />Explicit responsibilities</li><li><FileCheck2 />Traceable approvals and actions</li></ul><small>{asset.disclosure}</small></div><div className="studio-product-screen"><span>LIVE PRODUCT VIEW</span><div className="studio-screenshot" /></div></article>;
  }
  if (asset.slug === "dashboard-mockup") {
    return <article {...common}><div className="studio-mockup-heading"><AssetBrand inverse /><span>REAL INTERFACE · SYNTHETIC DEMO DATA</span></div><div className="studio-device"><div className="studio-device-bar"><i /><i /><i /><small>Perfect Match QMS · Tenant workspace</small></div><div className="studio-screenshot" /></div><div className="studio-mockup-caption"><strong>Priorities, evidence and governed work—visible in context.</strong><small>{asset.disclosure}</small></div></article>;
  }
  if (asset.slug === "quality-linkedin") {
    return <article {...common}><div className="studio-linkedin-copy"><AssetBrand /><p className="studio-kicker">QUALITY MANAGEMENT</p><h2>Good quality work is not more paperwork.</h2><p>It is clear responsibility, controlled evidence and improvement that can be traced.</p><span>#QualityManagement&nbsp;&nbsp;#QMS</span></div><span className="studio-disclosure">Conceptual brand visual</span></article>;
  }
  if (asset.slug === "audit-readiness") {
    return <article {...common}><AssetBrand inverse /><div className="studio-audit-copy"><p className="studio-kicker">AUDIT READINESS</p><h2>From scope to evidence,<br />keep every decision traceable.</h2><div><span><Layers3 />Plan the scope</span><span><ScanSearch />Review evidence</span><span><CheckCircle2 />Follow findings</span></div><small>{asset.disclosure}</small></div></article>;
  }
  return <article {...common}><AssetBrand /><div className="studio-infographic-heading"><p className="studio-kicker">ONE CONNECTED QMS</p><h2>Operate quality. Preserve evidence. Improve continuously.</h2></div><div className="studio-capability-grid"><span><Layers3 /><strong>Processes</strong><small>Scope and ownership</small></span><span><FileCheck2 /><strong>Documents</strong><small>Controlled revisions</small></span><span><ListChecks /><strong>Controls</strong><small>Implementation and proof</small></span><span><ScanSearch /><strong>Risks</strong><small>Assessment and follow-up</small></span><span><ClipboardCheck /><strong>Nonconformities</strong><small>Containment and investigation</small></span><span><Sparkles /><strong>Corrective actions</strong><small>Cause, action and effectiveness</small></span></div><span className="studio-disclosure">Capabilities documented in the current SaaS foundation</span></article>;
}

export default async function DesignStudioPage({ searchParams }: PageProps) {
  const { asset: requestedAsset } = await searchParams;
  const exportAsset = designAssetCatalog.find(({ slug }) => slug === requestedAsset);
  if (exportAsset) {
    return <main className="studio-export-shell"><DesignCanvas asset={exportAsset} exportMode /></main>;
  }
  return (
    <main className="studio-page">
      <header className="studio-page-header">
        <Link href="/products"><ArrowLeft aria-hidden="true" size={18} />Products</Link>
        <Link className="studio-page-brand" href="/"><BrandMark /><span><strong>PERFECT MATCH QMS</strong><small>Quality Operations Cloud</small></span></Link>
        <div className="studio-page-tools"><span className="studio-status"><ShieldCheck aria-hidden="true" size={16} />Draft collection</span><ThemeToggle /></div>
      </header>
      <section className="studio-intro"><p className="studio-kicker">THE PERFECT MATCH VISUAL LIBRARY</p><h1>AI Design Studio</h1><p>Explore six brand and product visuals. Download the original PNGs for review, from a real workspace preview to illustrations of connected quality work.</p><span className="studio-review-note"><ShieldCheck aria-hidden="true" size={16} />Draft assets · human approval required before publishing</span></section>
      <section className="studio-gallery" aria-label="Initial Perfect Match QMS visual assets">
        {designAssetCatalog.map((asset) => <figure key={asset.slug}><div className="studio-preview-frame"><Image alt={asset.purpose} height={asset.height} loading="eager" src={`/brand/design-studio/demo/${asset.slug}.png`} unoptimized width={asset.width} /></div><figcaption><div className="studio-asset-details"><strong>{asset.title}</strong><small>{asset.width} × {asset.height} · PNG</small><small>{asset.disclosure}</small></div><a className="studio-download" download={`${asset.slug}.png`} href={`/brand/design-studio/demo/${asset.slug}.png`} aria-label={`Download PNG: ${asset.title}`}><Download aria-hidden="true" size={16} />Download PNG</a></figcaption></figure>)}
      </section>
    </main>
  );
}
