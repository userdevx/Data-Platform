import { useEffect, useState } from "react";
import { getEngineStatus } from "../bridge/engineBridge";
import type { AppMode, EngineStatus } from "../types/appTypes";

function RightPanel({ activeMode }: { activeMode: AppMode }) {
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);

  async function loadStatus() {
    try {
      const status = await getEngineStatus();
      setEngineStatus(status);
    } catch {
      setEngineStatus(null);
    }
  }

  useEffect(() => {
    loadStatus();

    const timer = window.setInterval(() => {
      loadStatus();
    }, 3000);

    return () => window.clearInterval(timer);
  }, []);

  if (activeMode === "user") {
    return <ExternalUserRightPanel engineStatus={engineStatus} />;
  }

  return <InternalDeveloperRightPanel engineStatus={engineStatus} />;
}

function InternalDeveloperRightPanel({
  engineStatus
}: {
  engineStatus: EngineStatus | null;
}) {
  return (
    <aside className="right-panel">
      <section className="side-card">
        <h3>Source Metadata</h3>
        <p><strong>Name:</strong> Data Engine Records</p>
        <p><strong>Format:</strong> JSONL</p>
        <p><strong>Path:</strong> {engineStatus?.records_path ?? "checking..."}</p>
      </section>

      <section className="side-card">
        <h3>Health Metrics</h3>
        <p><strong>Status:</strong> {engineStatus?.status ?? "checking"}</p>
        <p><strong>Records:</strong> {engineStatus?.record_count ?? 0}</p>
        <p><strong>Bridge:</strong> active</p>
      </section>

      <section className="side-card">
        <h3>Validation Schema</h3>
        <p><strong>Required:</strong> source, category, data_type</p>
        <p><strong>Format:</strong> normalized record</p>
      </section>

      <section className="side-card warning">
        <h3>Next System Step</h3>
        <p>Add query controls and connect the console input.</p>
      </section>
    </aside>
  );
}

function ExternalUserRightPanel({
  engineStatus
}: {
  engineStatus: EngineStatus | null;
}) {
  return (
    <aside className="right-panel">
      <section className="side-card">
        <h3>Filter Presets</h3>
        <p><strong>Date:</strong> Recent Records</p>
        <p><strong>Source:</strong> All</p>
        <p><strong>Mode:</strong> User</p>
      </section>

      <section className="side-card">
        <h3>Data Freshness</h3>
        <p><strong>Status:</strong> {engineStatus?.status ?? "checking"}</p>
        <p><strong>Records:</strong> {engineStatus?.record_count ?? 0}</p>
      </section>

      <section className="side-card">
        <h3>Actions</h3>
        <button className="action-button">Download CSV</button>
        <button className="action-button secondary">Download PDF</button>
      </section>
    </aside>
  );
}

export default RightPanel;
