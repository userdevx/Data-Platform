export type OutputLogItem = {
  id: string;
  status: string;
  message: string;
  time: string;
};


export type IntelligenceOutputPanelProps = {
  logs: OutputLogItem[];
  onClear: () => void;
};


export default function IntelligenceOutputPanel({
  logs,
  onClear,
}: IntelligenceOutputPanelProps) {
  return (
    <section className="panel output-panel">
      <div className="output-header">
        <h2>
          Activity
        </h2>

        <button
          type="button"
          className="ghost-button"
          onClick={onClear}
        >
          Clear
        </button>
      </div>

      {logs.length > 0 ? (
        <div className="log-list">
          {logs.map(
            (item) => (
              <div
                className="log-row"
                key={item.id}
              >
                <span
                  className={
                    `log-dot log-${
                      item.status
                    }`
                  }
                />

                <span>
                  {item.message}
                </span>

                <time>
                  {item.time}
                </time>
              </div>
            ),
          )}
        </div>
      ) : (
        <p className="empty-log">
          No activity yet.
        </p>
      )}
    </section>
  );
}
