"use client";

import { HardDrive, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { RecordWorkspaceSkeleton } from "./record-workspace-skeleton";

const capacityMessages = {
  normal: "Within your contracted allowance",
  notice: "You have reached 80% of your allowance",
  warning: "You have reached 90% of your allowance",
  at_limit: "You have reached your allowance",
  over_limit: "Usage exceeds your allowance",
} as const;
type ConfiguredCapacity = {
  allowance_bytes: number;
  available_bytes: number;
  usage_percent: number;
  usage_status: keyof typeof capacityMessages;
};
type Usage = { tenant_id: string; recorded_bytes: number; document_file_count: number } & (
  ConfiguredCapacity | { allowance_bytes: null; available_bytes: null; usage_percent: null; usage_status: "unconfigured" }
);
type UsageState = { kind: "loading" } | { kind: "unavailable" } | { kind: "ready"; usage: Usage };
const decimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat("en-US");

function formatUsage(bytes: number) {
  return bytes > 0 && bytes < 10_000 ? "Less than 0.01 MB" : `${decimal.format(bytes / 1_000_000)} MB`;
}

function validCapacity(usage: Usage) {
  if (usage.usage_status === "unconfigured") {
    return usage.allowance_bytes === null && usage.available_bytes === null && usage.usage_percent === null;
  }
  return Object.hasOwn(capacityMessages, usage.usage_status)
    && Number.isSafeInteger(usage.allowance_bytes) && usage.allowance_bytes > 0
    && usage.available_bytes === Math.max(0, usage.allowance_bytes - usage.recorded_bytes)
    && Number.isSafeInteger(usage.usage_percent) && usage.usage_percent >= 0 && usage.usage_percent <= 100;
}

function CapacityNotice({ usage }: { usage: ConfiguredCapacity & { recorded_bytes: number } }) {
  const overage = usage.recorded_bytes - usage.allowance_bytes;
  return <section className="cc-card cc-capacity" data-status={usage.usage_status} aria-labelledby="storage-capacity-heading">
    <header>
      <h3 id="storage-capacity-heading">Capacity used by recorded PDFs</h3>
      <strong>{usage.usage_status === "over_limit" ? "Over capacity" : `${usage.usage_percent}%`}</strong>
    </header>
    <meter aria-label="Percentage of allowance used by PDFs" min={0} max={100} value={usage.usage_percent} />
    <p>{capacityMessages[usage.usage_status]}.
      {overage > 0 && <> Recorded PDFs use {formatUsage(overage)} more than the allowance.</>}
    </p>
  </section>;
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
          || !Number.isSafeInteger(usage.document_file_count) || usage.document_file_count < 0 || !validCapacity(usage)) {
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
        {state.usage.usage_status === "unconfigured"
          ? <dd>Pending activation<span>The company’s contracted capacity will appear when activated.</span></dd>
          : <dd>{formatUsage(state.usage.allowance_bytes)}<span>{formatUsage(state.usage.available_bytes)} available based on recorded PDFs</span></dd>}
      </div>
    </dl>}
    {state.kind === "ready" && state.usage.usage_status !== "unconfigured" && <CapacityNotice usage={state.usage} />}
    <section className="cc-card" aria-labelledby="storage-measurement-heading">
      <h3 id="storage-measurement-heading">What is measured</h3>
      <p>PDFs recorded as clean in Document control count here. Photos, backups, quarantined files and other attachments are outside this measurement. One MB is 1,000,000 bytes.</p>
    </section>
  </section>;
}
