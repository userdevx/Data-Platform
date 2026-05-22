import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";

type WorkspacePageProps = {
  databaseName: string;
  databasePath: string;
  onClose: () => void;
};

type WorkspaceDashboard = {
  connected_sources: number;
  raw_records: number;
  databases: number;
  data_quality: string;
  storage_used: string;
  active_database: string;
  recent_ingestion_source: string;
  recent_ingestion_status: string;
  pipeline_raw_to_bronze: string;
  pipeline_bronze_to_silver: string;
  pipeline_silver_to_gold: string;
};

type WorkspaceOutput = {
  title: string;
  message: string;
  rows: Record<string, string>[];
};

const sidebarItems = [
  "Dashboard",
  "Sources",
  "Data Drive",
  "Lakehouse",
  "Raw",
  "Bronze",
  "Silver",
  "Gold",
  "Pipelines",
  "Queries",
  "Data Quality",
  "Logs",
  "Console",
  "Settings"
];

function getColumns(rows: Record<string, string>[]) {
  if (rows.length === 0) {
    return [];
  }

  const firstRow = rows[0];

  if ("log_id" in firstRow) {
    return ["log_id", "log_file", "timestamp", "level", "action", "message", "source"];
  }

  if ("export_file" in firstRow) {
    return ["export_file", "format", "opens_with", "status"];
  }

  return Object.keys(firstRow);
}

function WorkspacePage({ databaseName, databasePath, onClose }: WorkspacePageProps) {
  const [activeSection, setActiveSection] = useState("Dashboard");

  const [dashboard, setDashboard] = useState<WorkspaceDashboard>({
    connected_sources: 0,
    raw_records: 0,
    databases: 0,
    data_quality: "0% No Data",
    storage_used: "0 B",
    active_database: databaseName || "Data Engine Database",
    recent_ingestion_source: "None",
    recent_ingestion_status: "Waiting",
    pipeline_raw_to_bronze: "Waiting",
    pipeline_bronze_to_silver: "Waiting",
    pipeline_silver_to_gold: "Waiting"
  });

  const [output, setOutput] = useState<WorkspaceOutput>({
    title: "Workspace",
    message: "Workspace ready.",
    rows: []
  });

  async function refreshDashboard() {
    try {
      const result = await invoke<WorkspaceDashboard>("workspace_refresh", {
        databaseName,
        databasePath
      });

      setDashboard(result);
      setOutput({
        title: "Refresh",
        message: "Dashboard refreshed from real Data Engine state.",
        rows: []
      });
    } catch (error) {
      showError(error);
    }
  }

  async function runAction(action: string, nextSection?: string) {
    try {
      if (nextSection) {
        setActiveSection(nextSection);
      }

      const result = await invoke<WorkspaceOutput>("workspace_action", {
        action,
        databaseName,
        databasePath
      });

      setOutput(result);

      const refreshed = await invoke<WorkspaceDashboard>("workspace_refresh", {
        databaseName,
        databasePath
      });

      setDashboard(refreshed);
    } catch (error) {
      showError(error);
    }
  }

  function showError(error: unknown) {
    setOutput({
      title: "Error",
      message: error instanceof Error ? error.message : String(error),
      rows: []
    });
  }

  useEffect(() => {
    void refreshDashboard();
  }, []);

  const outputColumns = getColumns(output.rows);

  return (
    <main className="workspace-page">
      <aside className="workspace-sidebar">
        <header className="workspace-brand">
          <div className="brand-icon">▣</div>
          <strong>Data Platform</strong>
        </header>

        <nav className="workspace-nav">
          {sidebarItems.map((item) => (
            <button
              key={item}
              type="button"
              className={activeSection === item ? "nav-item active" : "nav-item"}
              onClick={() => void runAction(item, item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace-main">
        <header className="workspace-header">
          <div>
            <h1>{activeSection}</h1>
            <p>
              Active database:{" "}
              <strong>{dashboard.active_database || databaseName}</strong>
            </p>
          </div>

          <div className="workspace-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => void refreshDashboard()}
            >
              Refresh
            </button>

            <button
              type="button"
              className="primary-button"
              onClick={() => void runAction("Run Pipeline", "Pipelines")}
            >
              Run Pipeline
            </button>

            <button
              type="button"
              className="primary-button"
              onClick={() => void runAction("Run Query", "Queries")}
            >
              Run Query
            </button>
          </div>
        </header>

        <section className="workspace-metrics">
          <article className="metric-card">
            <span>Connected Sources</span>
            <strong>{dashboard.connected_sources}</strong>
            <small>Actual source records</small>
          </article>

          <article className="metric-card">
            <span>Records Raw</span>
            <strong>{dashboard.raw_records}</strong>
            <small>Actual raw records</small>
          </article>

          <article className="metric-card">
            <span>Databases</span>
            <strong>{dashboard.databases}</strong>
            <small>Created databases</small>
          </article>

          <article className="metric-card">
            <span>Data Quality</span>
            <strong>{dashboard.data_quality}</strong>
            <small>Calculated from raw records</small>
          </article>

          <article className="metric-card">
            <span>Storage Used</span>
            <strong>{dashboard.storage_used}</strong>
            <small>Actual Data Drive size</small>
          </article>
        </section>

        <section className="workspace-grid">
          <article className="workspace-panel">
            <h2>Recent Ingestion</h2>

            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Records</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                <tr>
                  <td>{dashboard.recent_ingestion_source}</td>
                  <td>{dashboard.raw_records}</td>
                  <td className={dashboard.recent_ingestion_status === "Success" ? "success-text" : ""}>
                    {dashboard.recent_ingestion_status}
                  </td>
                </tr>
              </tbody>
            </table>

            <button
              type="button"
              className="secondary-button panel-button"
              onClick={() => void runAction("Sources", "Sources")}
            >
              View All Sources
            </button>
          </article>

          <article className="workspace-panel">
            <h2>Pipeline Status</h2>

            <div className="pipeline-row">
              <span>Raw → Bronze</span>
              <strong className={dashboard.pipeline_raw_to_bronze === "Success" ? "success-text" : ""}>
                {dashboard.pipeline_raw_to_bronze}
              </strong>
            </div>

            <div className="pipeline-row">
              <span>Bronze → Silver</span>
              <strong className={dashboard.pipeline_bronze_to_silver === "Success" ? "success-text" : ""}>
                {dashboard.pipeline_bronze_to_silver}
              </strong>
            </div>

            <div className="pipeline-row">
              <span>Silver → Gold</span>
              <strong className={dashboard.pipeline_silver_to_gold === "Success" ? "success-text" : ""}>
                {dashboard.pipeline_silver_to_gold}
              </strong>
            </div>

            <button
              type="button"
              className="secondary-button panel-button"
              onClick={() => void runAction("Pipelines", "Pipelines")}
            >
              View Pipelines
            </button>
          </article>

          <article className="workspace-panel">
            <h2>Recent Queries</h2>

            <p className="query-line">SELECT * FROM records LIMIT 100</p>
            <p className="query-line">SELECT COUNT(*) FROM sources</p>

            <button
              type="button"
              className="secondary-button panel-button"
              onClick={() => void runAction("Run Query", "Queries")}
            >
              Run New Query
            </button>
          </article>
        </section>

        <section className="workspace-panel logs-panel">
          <h2>{output.title}</h2>
          <p>{output.message}</p>

          {output.rows.length > 0 ? (
            <div className="workspace-table-wrap">
              <table className="workspace-output-table">
                <thead>
                  <tr>
                    {outputColumns.map((key) => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {output.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {outputColumns.map((key) => (
                        <td key={key}>{row[key] || ""}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <div className="workspace-footer-actions">
            <button
              type="button"
              className="secondary-button"
              onClick={() => void runAction("Logs", "Logs")}
            >
              View Logs
            </button>

            <button
              type="button"
              className="secondary-button"
              onClick={() => void runAction("Export", "Export")}
            >
              Export
            </button>

            <button type="button" className="quiet-button" onClick={onClose}>
              Close
            </button>
          </div>
        </section>
      </section>
    </main>
  );
}

export default WorkspacePage;
