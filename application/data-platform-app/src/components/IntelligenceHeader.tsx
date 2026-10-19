import { BRAND } from "../config/brand";
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
    <section className="intelligence-header" aria-label={title}>
      <div>
        <h1 className="eyebrow intelligence-brand">
          {BRAND.product}
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
