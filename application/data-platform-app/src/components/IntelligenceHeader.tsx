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
          Ask one question. Select automatic
          routing, a local model, or an
          available cloud model.
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
