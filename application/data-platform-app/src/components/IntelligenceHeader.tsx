export type IntelligenceHeaderProps = {
  title: string;
  runtimeStatus: string;
  statusLabel: string;
};


export default function IntelligenceHeader({
  title,
  runtimeStatus,
  statusLabel,
}: IntelligenceHeaderProps) {
  return (
    <section className="intelligence-header">
      <div>
        <p className="eyebrow">
          Data Platform
        </p>

        <h1>
          {title}
        </h1>

        <p className="page-subtitle">
          Ask, search, and understand your data.
        </p>
      </div>

      <div
        className={
          `compact-runtime-status `
          + `status-${runtimeStatus}`
        }
      >
        <span className="status-dot" />

        <span>
          {statusLabel}
        </span>
      </div>
    </section>
  );
}
