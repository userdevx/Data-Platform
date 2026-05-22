type StatusCardProps = {
  label: string;
  value: string;
  helper?: string;
};

function StatusCard({ label, value, helper }: StatusCardProps) {
  return (
    <section className="status-card">
      <p>{label}</p>
      <strong>{value}</strong>
      {helper ? <span>{helper}</span> : null}
    </section>
  );
}

export default StatusCard;
