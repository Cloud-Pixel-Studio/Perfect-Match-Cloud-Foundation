"use client";

export function RecordWorkspaceSkeleton({ label }: { label: string }) {
  return <div className="record-skeleton" role="status">
    <span className="sr-only">{label}</span>
    <div className="record-skeleton-toolbar" aria-hidden="true">
      <span className="skeleton-line" /><span className="skeleton-line" />
      <span className="skeleton-line" /><span className="skeleton-line" />
    </div>
    <div className="record-skeleton-grid" aria-hidden="true">
      <div className="record-skeleton-list">
        {[0, 1, 2].map((item) => <div className="record-skeleton-card" key={item}>
          <span className="skeleton-line skeleton-line-title" />
          <span className="skeleton-line" /><span className="skeleton-line skeleton-line-short" />
        </div>)}
      </div>
      <div className="record-skeleton-detail">
        <span className="skeleton-line skeleton-line-title" />
        <span className="skeleton-line" /><span className="skeleton-line" />
        <span className="skeleton-line skeleton-line-short" />
        <div className="record-skeleton-panel" />
      </div>
    </div>
  </div>;
}
