"use client";

import { Database, HardDrive, Server } from "lucide-react";
import { useEffect, useState } from "react";

import { foundationLabel, type FoundationState } from "../lib/foundation";

type ApiHealth = {
  status: string;
  version: string;
  dependencies: { database: string; object_storage: string };
};

export function RuntimeStatus() {
  const [state, setState] = useState<FoundationState>("checking");
  const [health, setHealth] = useState<ApiHealth | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/platform-health", { signal: controller.signal })
      .then(async (response) => {
        const data = (await response.json()) as ApiHealth;
        setHealth(data);
        setState(response.ok ? "ready" : "unavailable");
      })
      .catch(() => setState("unavailable"));
    return () => controller.abort();
  }, []);

  const checks = [
    { label: "API service", value: health?.status ?? state, icon: Server },
    { label: "PostgreSQL", value: health?.dependencies.database ?? state, icon: Database },
    {
      label: "Object storage",
      value: health?.dependencies.object_storage ?? state,
      icon: HardDrive,
    },
  ];

  return (
    <section className="runtime-panel" aria-labelledby="runtime-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Local environment</p>
          <h2 id="runtime-heading">Runtime status</h2>
        </div>
        <span className={`status-badge status-${state}`}>
          <span className="status-dot" aria-hidden="true" />
          {foundationLabel(state)}
        </span>
      </div>
      <div className="status-grid">
        {checks.map(({ label, value, icon: Icon }) => (
          <article className="status-item" key={label}>
            <span className="status-icon">
              <Icon aria-hidden="true" size={19} strokeWidth={1.8} />
            </span>
            <div>
              <h3>{label}</h3>
              <p>{value === "ok" ? "Connected" : foundationLabel(state)}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
