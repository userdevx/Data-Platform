type StatusItem = {
  label: string;
  value: string;
  status: string;
};


const STATUS_ITEMS: StatusItem[] = [
  {
    label: "Sources",
    value: "1",
    status: "Connected",
  },
  {
    label: "Raw Records",
    value: "1",
    status: "Ready",
  },
  {
    label: "Definitions",
    value: "Active",
    status: "Ready",
  },
  {
    label: "Validation",
    value: "Enabled",
    status: "Ready",
  },
  {
    label: "Runtime",
    value: "Active",
    status: "Ready",
  },
];


function StatusCard({
  item,
}: {
  item: StatusItem;
}) {
  return (
    <article className="metric-card metric-card-clean">
      <div>
        <p>{item.label}</p>
        <strong>{item.value}</strong>
        <small>{item.status}</small>
      </div>
    </article>
  );
}


export default function PlatformStatusStrip() {
  return (
    <section
      className="metric-grid metric-grid-clean"
      aria-label="Platform status"
    >
      {STATUS_ITEMS.map(
        (item) => (
          <StatusCard
            key={item.label}
            item={item}
          />
        ),
      )}
    </section>
  );
}
