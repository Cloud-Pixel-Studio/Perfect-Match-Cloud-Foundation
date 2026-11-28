"use client";

import { HardDrive, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

type Usage = { tenant_id: string; recorded_bytes: number; document_file_count: number };
type UsageState = { kind: "loading" } | { kind: "unavailable" } | { kind: "ready"; usage: Usage };
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("en-US");

function formatUsage(bytes: number) {
  return bytes > 0 && bytes < 10_000 ? "Less than 0.01 MB" : `${decimal.format(bytes / 1_000_000)} MB`;
}

export function CompanyStorageWorkspace({ tenantId, company }: { tenantId: string; company: string }) {
  const [state, setState] = useState<UsageState>({ kind: "loading" });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const response = await fetch(`/api/identity/company-storage/${tenantId}`, {
          credentials: "include", cache: "no-store", signal,
        });
        if (!response.ok || response.headers.get("X-Tenant-ID") !== tenantId) throw new Error("Usage unavailable");
        const usage = await response.json() as Usage;
        if (usage.tenant_id !== tenantId || !Number.isSafeInteger(usage.recorded_bytes) || usage.recorded_bytes < 0
          || !Number.isSafeInteger(usage.document_file_count) || usage.document_file_count < 0) {
          throw new Error("Invalid company usage");
        }
        if (!signal.aborted) setState({ kind: "ready", usage });
      } catch {
        if (!signal.aborted) setState({ kind: "unavailable" });
      }
    }
    void load();
    return () => controller.abort();
  }, [tenantId, revision]);

  function refresh() {
    setState({ kind: "loading" });
    setRevision(current => current + 1);
  }

  return <section className="cc-workspace" aria-labelledby="company-storage-heading">
    <header className="cc-workspace-header">
      <span className="cc-icon"><HardDrive aria-hidden="true" size={23} /></span>
      <div>
        <p className="cc-overline">{company}</p>
        <h2 id="company-storage-heading">Storage usage</h2>
        <p>Review the space occupied by this company’s recorded document files.</p>
      </div>
      <button className="cc-secondary" type="button" disabled={state.kind === "loading"} onClick={refresh}>
        <RefreshCw aria-hidden="true" size={17} /> Refresh usage
      </button>
    </header>
    {state.kind === "loading" && <RecordWorkspaceSkeleton label="Loading company storage usage" />}
    {state.kind === "unavailable" && <p className="cc-card" role="alert">Company storage usage could not be loaded. Refresh to retry.</p>}
    {state.kind === "ready" && <dl className="cc-profile-grid cc-storage-metrics" aria-label="Company document storage totals" aria-live="polite">
      <div className="cc-card">
        <dt>Recorded document storage</dt>
        <dd>{formatUsage(state.usage.recorded_bytes)}<span>{integer.format(state.usage.recorded_bytes)} bytes</span></dd>
      </div>
      <div className="cc-card">
        <dt>Retained PDF files</dt>
        <dd>{integer.format(state.usage.document_file_count)}<span>Includes prior revisions you keep.</span></dd>
      </div>
      <div className="cc-card">
        <dt>Contracted allowance</dt>
        <dd>Pending activation<span>The company’s contracted capacity will appear when activated.</span></dd>
      </div>
    </dl>}
    <section className="cc-card" aria-labelledby="storage-measurement-heading">
      <h3 id="storage-measurement-heading">What is measured</h3>
      <p>PDFs recorded as clean in Document control count here. Photos, backups, quarantined files and other attachments are outside this measurement. One MB is 1,000,000 bytes.</p>
    </section>
  </section>;
}
