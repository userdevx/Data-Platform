import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useEffect, useState } from "react";
import "./ButtonInterfacePage.css";

type ViewMode = "workspace" | "data" | "paige";

type ConnectionResult = {
  success: boolean;
  message: string;
  source_type: string;
  path: string | null;
  storage_path: string | null;
};

type CreateDatabaseResult = {
  success: boolean;
  message: string;
  database_name: string;
  database_path: string;
  source_file: string;
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

type PaigeSearchResult = {
  title: string;
  url: string;
  domain: string;
};

type PaigeOutput = {
  input?: string;
  action?: string;
  result?: string;
  results?: PaigeSearchResult[];
  timestamp?: string;
  status?: string;
};

type OverlayState = {
  active: boolean;
  title: string;
  message: string;
};

const emptyDashboard: WorkspaceDashboard = {
  connected_sources: 0,
  raw_records: 0,
  databases: 0,
  data_quality: "0% No Data",
  storage_used: "0 B",
  active_database: "Data Platform",
  recent_ingestion_source: "None",
  recent_ingestion_status: "Waiting",
  pipeline_raw_to_bronze: "Waiting",
  pipeline_bronze_to_silver: "Waiting",
  pipeline_silver_to_gold: "Waiting"
};

function getFileName(path: string) {
  return path.split("/").pop() || path;
}

function createDatabaseName(path: string) {
  const fileName = getFileName(path);

  return (
    fileName
      .replace(/\.[^/.]+$/, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "database"
  );
}

function getColumns(rows: Record<string, string>[]) {
  if (rows.length === 0) {
    return [];
  }

  return Object.keys(rows[0]);
}

function cleanUrl(url: string) {
  if (!url) {
    return "";
  }

  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }

  if (url.startsWith("//")) {
    return `https:${url}`;
  }

  return `https://${url}`;
}

function Spinner() {
  return <span className="spinner" aria-hidden="true"></span>;
}

export default function ButtonInterfacePage() {
  const [viewMode, setViewMode] = useState<ViewMode>("workspace");

  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [dataDrivePath, setDataDrivePath] = useState("");
  const [databaseName, setDatabaseName] = useState("");
  const [databasePath, setDatabasePath] = useState("");

  const [dashboard, setDashboard] = useState<WorkspaceDashboard>(emptyDashboard);
  const [output, setOutput] = useState<WorkspaceOutput>({
    title: "Output",
    message: "Ready.",
    rows: []
  });

  const [status, setStatus] = useState("Ready.");
  const [successMessage, setSuccessMessage] = useState("");
  const [overlay, setOverlay] = useState<OverlayState>({
    active: false,
    title: "",
    message: ""
  });

  const [isCreatingDatabase, setIsCreatingDatabase] = useState(false);
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [isRunningQuery, setIsRunningQuery] = useState(false);

  const [question, setQuestion] = useState("");
  const [paigeStatus, setPaigeStatus] = useState("Paige is ready.");
  const [paigeOutput, setPaigeOutput] = useState<PaigeOutput | null>(null);
  const [isAsking, setIsAsking] = useState(false);

  const hasSelectedFile = selectedFilePath.trim().length > 0;
  const hasDatabase = databasePath.trim().length > 0 || dashboard.databases > 0;
  const canCreateDatabase = hasSelectedFile && databaseName.trim().length > 0;
  const canRunEngineAction = hasDatabase || dashboard.raw_records > 0;

  function showOverlay(title: string, message: string) {
    setOverlay({
      active: true,
      title,
      message
    });
  }

  function hideOverlay() {
    setOverlay({
      active: false,
      title: "",
      message: ""
    });
  }

  function showSuccess(message: string) {
    setSuccessMessage(message);

    window.setTimeout(() => {
      setSuccessMessage("");
    }, 3500);
  }

  async function refreshDashboard() {
    try {
      const result = await invoke<WorkspaceDashboard>("workspace_refresh", {
        databaseName,
        databasePath
      });

      setDashboard(result);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  }

  async function chooseFile() {
    try {
      setStatus("Opening file picker...");

      const selected = await open({
        multiple: false,
        directory: false,
        title: "Choose a file"
      });

      if (typeof selected !== "string") {
        setStatus("No file selected.");
        return;
      }

      setSelectedFilePath(selected);
      setDatabaseName(createDatabaseName(selected));
      setDataDrivePath("");
      setStatus("File selected.");
      showSuccess("File selected.");
      setViewMode("data");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  }

  async function connectSelectedFile() {
    if (!selectedFilePath) {
      throw new Error("Choose a file first.");
    }

    const result = await invoke<ConnectionResult>("connect_data", {
      sourceType: "files",
      path: selectedFilePath
    });

    if (!result.success) {
      throw new Error(result.message || "Connection failed.");
    }

    const storedPath = result.storage_path || selectedFilePath;
    setDataDrivePath(storedPath);

    return storedPath;
  }

  async function createDatabase() {
    if (!selectedFilePath) {
      setStatus("Choose a file first.");
      setViewMode("data");
      return;
    }

    if (!databaseName.trim()) {
      setStatus("Enter a database name.");
      setViewMode("data");
      return;
    }

    try {
      setIsCreatingDatabase(true);
      showOverlay("Creating database", "Connecting your file and preparing the Data Engine database...");
      setStatus("Creating database...");

      const sourcePath = dataDrivePath || (await connectSelectedFile());

      const result = await invoke<CreateDatabaseResult>("create_database", {
        databaseName,
        selectedFilePath: sourcePath,
        storageType: "Data Engine Database"
      });

      if (!result.success) {
        setStatus(result.message || "Database creation failed.");
        return;
      }

      setDatabaseName(result.database_name);
      setDatabasePath(result.database_path);
      setStatus("Database created.");
      showSuccess("Database created.");
      setOutput({
        title: "Database Created",
        message: "Database created and dashboard updated.",
        rows: [
          {
            database_name: result.database_name,
            database_path: result.database_path,
            source_file: result.source_file,
            status: "created"
          }
        ]
      });

      setViewMode("workspace");
      await refreshDashboard();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setIsCreatingDatabase(false);
      hideOverlay();
    }
  }

  async function runPipeline() {
    if (!canRunEngineAction) {
      setStatus("Create a database or add raw records before running the pipeline.");
      return;
    }

    try {
      setIsRunningPipeline(true);
      showOverlay("Running pipeline", "Processing records through Raw, Bronze, Silver, and Gold layers...");
      setStatus("Running pipeline...");

      const result = await invoke<WorkspaceOutput>("workspace_action", {
        action: "Run Pipeline",
        databaseName,
        databasePath
      });

      setOutput(result);
      setStatus(result.message);
      showSuccess("Pipeline complete.");
      setViewMode("workspace");
      await refreshDashboard();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRunningPipeline(false);
      hideOverlay();
    }
  }

  async function runQuery() {
    if (!canRunEngineAction) {
      setStatus("Create a database or add records before running a query.");
      return;
    }

    try {
      setIsRunningQuery(true);
      showOverlay("Running query", "Reading records from the Data Engine...");
      setStatus("Running query...");

      const result = await invoke<WorkspaceOutput>("workspace_action", {
        action: "Run Query",
        databaseName,
        databasePath
      });

      setOutput(result);
      setStatus(result.message);
      showSuccess("Query complete.");
      setViewMode("workspace");
      await refreshDashboard();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRunningQuery(false);
      hideOverlay();
    }
  }

  async function askQuestion() {
    const cleanQuestion = question.trim();

    if (!cleanQuestion) {
      setPaigeStatus("Ask a question first.");
      setViewMode("paige");
      return;
    }

    try {
      setIsAsking(true);
      setPaigeOutput(null);
      showOverlay("Asking Paige", "Looking for a useful answer with sources...");
      setPaigeStatus("Looking for an answer...");

      await invoke<unknown>("start_agent_worker");

      await invoke<unknown>("submit_agent_task", {
        input: cleanQuestion
      });

      await pollForAnswer(cleanQuestion);
    } catch (error) {
      setPaigeStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setIsAsking(false);
      hideOverlay();
    }
  }

  async function pollForAnswer(expectedInput: string) {
    const maxAttempts = 20;
    const waitMs = 1000;

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        setPaigeStatus(`Working on it... ${attempt}/${maxAttempts}`);

        const raw = await invoke<string>("read_agent_output");
        const parsed = JSON.parse(raw) as PaigeOutput;

        const inputMatches =
          parsed.input?.trim().toLowerCase() === expectedInput.trim().toLowerCase();

        const isComplete = parsed.status === "complete" || parsed.status === "error";

        if (inputMatches && isComplete) {
          setPaigeOutput(parsed);
          setPaigeStatus(
            parsed.status === "complete" ? "Answer ready." : "Review the answer."
          );
          showSuccess(parsed.status === "complete" ? "Answer ready." : "Answer needs review.");
          setQuestion("");
          return;
        }
      } catch {
        // Keep waiting while the output file is being created.
      }

      await new Promise((resolve) => window.setTimeout(resolve, waitMs));
    }

    setPaigeStatus("No new answer appeared yet.");
  }

  async function openSource(url: string) {
    const finalUrl = cleanUrl(url);

    if (!finalUrl) {
      setPaigeStatus("This source does not have a valid link.");
      return;
    }

    try {
      await openUrl(finalUrl);
      showSuccess("Source opened.");
    } catch (error) {
      setPaigeStatus(error instanceof Error ? error.message : String(error));
    }
  }

  function submitQuestionOnEnter(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      void askQuestion();
    }
  }

  useEffect(() => {
    void refreshDashboard();
  }, []);

  const outputColumns = getColumns(output.rows);

  return (
    <main className="workspace-shell">
      {overlay.active ? (
        <section className="loading-overlay" aria-live="polite">
          <div className="loading-card">
            <Spinner />
            <h2>{overlay.title}</h2>
            <p>{overlay.message}</p>
          </div>
        </section>
      ) : null}

      {successMessage ? (
        <div className="success-toast" aria-live="polite">
          <span>✓</span>
          <strong>{successMessage}</strong>
        </div>
      ) : null}

      <aside className="workspace-sidebar">
        <header className="workspace-brand">
          <div className="workspace-logo">▣</div>

          <div>
            <strong>Data Platform</strong>
            <span>Interactive workspace</span>
          </div>
        </header>

        <nav className="workspace-nav" aria-label="Primary navigation">
          <button
            type="button"
            className={viewMode === "workspace" ? "active" : ""}
            onClick={() => setViewMode("workspace")}
          >
            Workspace
          </button>

          <button
            type="button"
            className={viewMode === "data" ? "active" : ""}
            onClick={() => setViewMode("data")}
          >
            Data
          </button>

          <button
            type="button"
            className={viewMode === "paige" ? "active" : ""}
            onClick={() => setViewMode("paige")}
          >
            Paige
          </button>
        </nav>

        <section className="workspace-status-box">
          <strong>Status</strong>
          <span>{status}</span>
        </section>
      </aside>

      <section className="workspace-main">
        <header className="workspace-header">
          <div>
            <p>Data Platform</p>

            <h1>
              {viewMode === "workspace"
                ? "Workspace"
                : viewMode === "data"
                  ? "Data Setup"
                  : "Paige"}
            </h1>
          </div>

          <div className="workspace-primary-actions">
            <button
              type="button"
              onClick={() => void runPipeline()}
              disabled={!canRunEngineAction || isRunningPipeline}
              title={!canRunEngineAction ? "Create a database first" : "Run pipeline"}
            >
              {isRunningPipeline ? (
                <>
                  <Spinner />
                  Running
                </>
              ) : (
                "Run Pipeline"
              )}
            </button>

            <button
              type="button"
              onClick={() => void runQuery()}
              disabled={!canRunEngineAction || isRunningQuery}
              title={!canRunEngineAction ? "Create a database first" : "Run query"}
            >
              {isRunningQuery ? (
                <>
                  <Spinner />
                  Querying
                </>
              ) : (
                "Run Query"
              )}
            </button>
          </div>
        </header>

        <section className="workspace-metrics" aria-label="System overview">
          <article>
            <span>Sources</span>
            <strong>{dashboard.connected_sources}</strong>
          </article>

          <article>
            <span>Raw Records</span>
            <strong>{dashboard.raw_records}</strong>
          </article>

          <article>
            <span>Databases</span>
            <strong>{dashboard.databases}</strong>
          </article>

          <article>
            <span>Quality</span>
            <strong>{dashboard.data_quality}</strong>
          </article>

          <article>
            <span>Storage</span>
            <strong>{dashboard.storage_used}</strong>
          </article>
        </section>

        {viewMode === "workspace" ? (
          <section className="workspace-grid">
            <article className="workspace-card">
              <h2>Pipeline</h2>

              <div className="pipeline-row">
                <span>Raw → Bronze</span>
                <strong>{dashboard.pipeline_raw_to_bronze}</strong>
              </div>

              <div className="pipeline-row">
                <span>Bronze → Silver</span>
                <strong>{dashboard.pipeline_bronze_to_silver}</strong>
              </div>

              <div className="pipeline-row">
                <span>Silver → Gold</span>
                <strong>{dashboard.pipeline_silver_to_gold}</strong>
              </div>
            </article>

            <article className="workspace-card">
              <h2>Recent Ingestion</h2>

              <div className="pipeline-row">
                <span>Source</span>
                <strong>{dashboard.recent_ingestion_source}</strong>
              </div>

              <div className="pipeline-row">
                <span>Records</span>
                <strong>{dashboard.raw_records}</strong>
              </div>

              <div className="pipeline-row">
                <span>Status</span>
                <strong>{dashboard.recent_ingestion_status}</strong>
              </div>
            </article>
          </section>
        ) : null}

        {viewMode === "data" ? (
          <section className="workspace-grid">
            <article className="workspace-card">
              <h2>Data Setup</h2>
              <p>Choose a file, name the database, then create it.</p>

              <label className="workspace-label">
                Selected file
                <input
                  value={selectedFilePath ? getFileName(selectedFilePath) : ""}
                  readOnly
                  placeholder="No file selected"
                />
              </label>

              <label className="workspace-label">
                Database name
                <input
                  value={databaseName}
                  onChange={(event) => setDatabaseName(event.target.value)}
                  placeholder="Enter database name"
                />
              </label>

              <div className="workspace-button-row">
                <button type="button" onClick={() => void chooseFile()}>
                  Choose File
                </button>

                <button
                  type="button"
                  className="primary"
                  onClick={() => void createDatabase()}
                  disabled={!canCreateDatabase || isCreatingDatabase}
                >
                  {isCreatingDatabase ? (
                    <>
                      <Spinner />
                      Creating
                    </>
                  ) : (
                    "Create Database"
                  )}
                </button>
              </div>
            </article>

            <article className="workspace-card">
              <h2>Storage</h2>

              <div className="storage-box">
                <strong>Data Drive</strong>
                <span>{dataDrivePath || "No connected file yet."}</span>
              </div>

              <div className="storage-box">
                <strong>Database</strong>
                <span>{databasePath || "No database created yet."}</span>
              </div>
            </article>
          </section>
        ) : null}

        {viewMode === "paige" ? (
          <section className="workspace-grid">
            <article className="workspace-card paige-card">
              <h2>Ask Paige</h2>
              <p>Ask a question and open source links when available.</p>

              <div className="paige-input-row">
                <input
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={submitQuestionOnEnter}
                  placeholder="Ask a question..."
                />

                <button
                  type="button"
                  className="primary"
                  onClick={() => void askQuestion()}
                  disabled={isAsking}
                >
                  {isAsking ? (
                    <>
                      <Spinner />
                      Searching
                    </>
                  ) : (
                    "Ask Question"
                  )}
                </button>
              </div>

              <p className="paige-status">{paigeStatus}</p>
            </article>

            <article className="workspace-card">
              <h2>Answer</h2>

              {paigeOutput ? (
                <>
                  <p>{paigeOutput.result || "No answer returned yet."}</p>

                  {paigeOutput.results && paigeOutput.results.length > 0 ? (
                    <div className="source-list">
                      {paigeOutput.results.map((result, index) => (
                        <button
                          key={`${result.url}-${index}`}
                          type="button"
                          className="source-row"
                          onClick={() => void openSource(result.url)}
                        >
                          <span>{index + 1}</span>
                          <strong>{result.title}</strong>
                          <small>{result.domain}</small>
                          <em>Open</em>
                        </button>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <p>No answer loaded yet.</p>
              )}
            </article>
          </section>
        ) : null}

        <section className="workspace-output">
          <div>
            <h2>{output.title}</h2>
            <p>{output.message}</p>
          </div>

          {output.rows.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {outputColumns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {output.rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {outputColumns.map((column) => (
                        <td key={column}>{row[column] || ""}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}
