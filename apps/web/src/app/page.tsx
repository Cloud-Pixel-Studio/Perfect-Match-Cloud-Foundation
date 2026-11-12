import { connection } from "next/server";

import { BrandMark } from "../components/brand-mark";
import { IdentityShell } from "../components/identity-shell";

export default async function Home() {
  await connection();
  return (
    <div className="identity-page">
      <header className="identity-brand">
        <BrandMark priority />
        <div>
          <strong>PERFECT MATCH QMS</strong>
          <span>Quality Operations Cloud</span>
        </div>
        <nav className="identity-public-nav" aria-label="Public pages"><a href="/products">Products</a></nav>
      </header>
      <IdentityShell />
      <footer className="identity-footer">
        <span>Perfect Match QMS</span>
        <span>Quality management workspace</span>
      </footer>
    </div>
  );
}
