import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { BrandMark } from "./brand-mark";
import { ThemeToggle } from "./theme-toggle";

const productLinks = [
  ["teams", "For your team"],
  ["platform", "The platform"],
  ["standards", "ISO addons"],
  ["security", "Security"],
] as const;

export function ProductHeader({ plansPage = false }: { plansPage?: boolean }) {
  const fragmentPrefix = plansPage ? "/products" : "";
  return (
    <header className="market-header">
      <Link className="market-brand" href="/">
        <BrandMark priority />
        <span><strong>PERFECT MATCH QMS</strong><small>Quality Operations Cloud</small></span>
      </Link>
      <nav className="market-navigation" aria-label="Product navigation">
        <a href={`${fragmentPrefix}#product-tour`}>Product tour</a>
        <Link href="/products/plans" aria-current={plansPage ? "page" : undefined}>Plans &amp; storage</Link>
        {productLinks.map(([id, label]) => <a key={id} href={`${fragmentPrefix}#${id}`}>{label}</a>)}
      </nav>
      <div className="market-header-actions">
        <ThemeToggle />
        <Link className="market-signin" href="/">Log in</Link>
        <a className="market-button market-button-small" href={`${fragmentPrefix}#demo`}>
          Request a demo <ArrowRight aria-hidden="true" size={15} />
        </a>
      </div>
    </header>
  );
}
