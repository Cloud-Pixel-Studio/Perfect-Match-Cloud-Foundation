import Image from "next/image";
import { connection } from "next/server";

import { IdentityShell } from "../components/identity-shell";

export default async function Home() {
  await connection();
  return (
    <div className="identity-page">
      <header className="identity-brand">
        <Image alt="" height={40} priority src="/brand-mark.png" unoptimized width={40} />
        <div>
          <strong>PERFECT MATCH</strong>
          <span>Quality Management Cloud</span>
        </div>
        <nav className="identity-public-nav" aria-label="Public pages"><a href="/products">Products</a></nav>
      </header>
      <IdentityShell />
      <footer className="identity-footer">
        <span>Perfect Match Cloud</span>
        <span>Quality management workspace</span>
      </footer>
    </div>
  );
}
