import { useEffect, useMemo, useState } from "react";
import StatusCard from "./StatusCard";
import { getEngineStatus, getRecentRecords } from "../bridge/engineBridge";
import type { AppMode, AppPage, DataRecord, EngineStatus } from "../types/appTypes";

type CenterWorkspaceProps = {
  activeMode: AppMode;
  activePage: AppPage;
};

function CenterWorkspace({ activeMode, activePage }: CenterWorkspaceProps) {
  const [records, setRecords] = useState<DataRecord[]>([]);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadEngineData() {
    try {
      setLoading(true);
      setErrorMessage("");

      const [status, recentRecords] = await Promise.all([
        getEngineStatus(),
        getRecentRecords(50)
      ]);

      setEngineStatus(status);
      setRecords(recentRecords);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadEngineData();

    const timer = window.setInterval(() => {
      loadEngineData();
    }, 3000);

    return () => window.clearInterval(timer);
  }, []);

  const dataTypeCount = useMemo(() => {
    return new Set(records.map((record) => record.data_type)).size;
  }, [records]);

  const sourceCount = useMemo(() => {
    return new Set(records.map((record) => record.source)).size;
  }, [records]);

  const latestRecord = records[0];

  return (
    <main className="center-workspace dashboard-workspace">
      <div className="workspace-header dashboard-header">
        <div>
          <p className="eyebrow">
            {activeMode === "developer" ? "Internal Developer Mode" : "External User Mode"}
          </p>
          <h1>{getPageTitle(activeMode, activePage)}</h1>
        </div>

        <div className="dashboard-search">
          <span>Search records, data types, queries...</span>
          <kbd>Ctrl K</kbd>
        </div>

        <div className="status-pill">
          {engineStatus?.status === "online" ? "Engine Online" : "Checking Engine"}
        </div>
      </div>

      {errorMessage ? (
        <section className="card error-card">
          <h2>Engine Bridge Error</h2>
          <p>{errorMessage}</p>
        </section>
      ) : null}

      <section className="status-grid dashboard-metrics">
        <StatusCard
          label="Total Records"
          value={`${engineStatus?.record_count ?? 0}`}
          helper="Data Engine file"
        />
        <StatusCard
          label="Recent Records"
          value={`${records.length}`}
          helper="Current view"
        />
        <StatusCard
          label="Data Types"
          value={`${dataTypeCount}`}
          helper="Detected information types"
        />
        <StatusCard
          label="Sources"
          value={`${sourceCount}`}
          helper="Connected inputs"
        />
      </section>

      <section className="dashboard-grid">
        <section className="card query-panel">
          <div className="card-header">
            <h2>Recent Query</h2>
            <button className="action-button compact-button">Run Query</button>
          </div>

          <div className="code-window">
            <div><span className="line-number">1</span><span className="keyword">SELECT</span> source, data_type, value, unit</div>
            <div><span className="line-number">2</span><span className="keyword">FROM</span> records</div>
            <div><span className="line-number">3</span><span className="keyword">WHERE</span> source = <span className="string">'system'</span></div>
            <div><span className="line-number">4</span><span className="keyword">ORDER BY</span> timestamp <span className="keyword">DESC</span></div>
            <div><span className="line-number">5</span><span className="keyword">LIMIT</span> 10;</div>
          </div>

          <div className="record-table query-results-table">
            <div className="table-row table-head">
              <span>Source</span>
              <span>Data Type</span>
              <span>Value</span>
              <span>Unit</span>
            </div>

            {records.slice(0, 5).map((record) => (
              <div className="table-row" key={record.id}>
                <span>{record.source}</span>
                <span>{record.data_type}</span>
                <span>{String(record.value)}</span>
                <span>{record.unit}</span>
              </div>
            ))}
          </div>

          <div className="query-footer">
            <span>{loading ? "Loading..." : "Query executed through Engine Bridge"}</span>
            <span>{records.slice(0, 5).length} rows returned</span>
          </div>
        </section>

        <section className="card tables-panel">
          <div className="card-header">
            <h2>Records</h2>
            <span>{records.length} visible</span>
          </div>

          <div className="table-search">Search records...</div>

          {records.length === 0 ? (
            <p className="empty-state">
              No records found. Run the Data Engine collector, then return to this interface.
            </p>
          ) : (
            <div className="records-list">
              {records.slice(0, 8).map((record) => (
                <div className="record-list-row" key={record.id}>
                  <div>
                    <strong>{record.data_type}</strong>
                    <span>{record.category}</span>
                  </div>
                  <div>{String(record.value)} {record.unit}</div>
                  <small>{record.source}</small>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="card ingestion-panel">
          <div className="card-header">
            <h2>Data Ingestion</h2>
            <span>Live window</span>
          </div>

          <div className="line-chart">
            <span style={{ height: "35%" }}></span>
            <span style={{ height: "58%" }}></span>
            <span style={{ height: "44%" }}></span>
            <span style={{ height: "66%" }}></span>
            <span style={{ height: "52%" }}></span>
            <span style={{ height: "78%" }}></span>
            <span style={{ height: "64%" }}></span>
            <span style={{ height: "88%" }}></span>
          </div>

          <div className="ingestion-meter">
            <div className="meter-fill"></div>
          </div>
        </section>

        <section className="card activity-panel">
          <div className="card-header">
            <h2>Recent Activity</h2>
            <span>Engine events</span>
          </div>

          <div className="activity-list">
            <div className="activity-row">
              <span className="activity-dot success"></span>
              <div>
                <strong>Engine Bridge connected</strong>
                <small>Status: {engineStatus?.status ?? "checking"}</small>
              </div>
            </div>

            <div className="activity-row">
              <span className="activity-dot success"></span>
              <div>
                <strong>Records loaded</strong>
                <small>{records.length} recent records returned</small>
              </div>
            </div>

            <div className="activity-row">
              <span className="activity-dot info"></span>
              <div>
                <strong>Latest data type</strong>
                <small>{latestRecord?.data_type ?? "No data type available"}</small>
              </div>
            </div>

            <div className="activity-row">
              <span className="activity-dot info"></span>
              <div>
                <strong>Storage flow ready</strong>
                <small>Raw Records → Validated → Indexed → Query</small>
              </div>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

function getPageTitle(activeMode: AppMode, activePage: AppPage): string {
  const developerTitles: Partial<Record<AppPage, string>> = {
    home: "Home",
    ingestion: "Live Ingestion",
    lakehouse: "Lakehouse Storage",
    query: "Query Viewer",
    processing: "Processing Pipelines",
    jobs: "Jobs / Logs",
    settings: "Settings"
  };

  const userTitles: Partial<Record<AppPage, string>> = {
    home: "Home",
    reports: "My Reports",
    query: "Query Viewer",
    settings: "Settings"
  };

  if (activeMode === "developer") {
    return developerTitles[activePage] || "Overview";
  }

  return userTitles[activePage] || "Overview";
}

export default CenterWorkspace;
