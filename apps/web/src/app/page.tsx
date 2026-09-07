import Image from "next/image";

import { IdentityShell } from "../components/identity-shell";

export default function Home() {
  return (
    <div className="identity-page">
      <header className="identity-brand">
        <Image alt="" height={40} priority src="/brand-mark.png" unoptimized width={40} />
        <div>
          <strong>PERFECT MATCH</strong>
          <span>Quality Management Cloud</span>
        </div>
      </header>
      <IdentityShell />
      <footer className="identity-footer">
        <span>Identity &amp; organization boundary</span>
        <span>PMC-01</span>
      </footer>
    </div>
  );
}
