import { useEffect, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  getIntelligenceDefinition,
  processNaturalIntelligenceRequest,
  type NaturalIntelligenceResponse,
} from "../bridge/intelligenceBridge";
import { intelligenceConfig } from "../config/intelligenceConfig";
import "../styles/intelligencePage.css";

type RuntimeStatus = "ready" | "thinking" | "success" | "error";

type SystemLogItem = {
  id: string;
  message: string;
  time: string;
  status: "success" | "info" | "error";
};

function getTimeLabel(): string {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function createLog(
  message: string,
  status: SystemLogItem["status"] = "info",
): SystemLogItem {
  return {
    id: crypto.randomUUID(),
    message,
    time: getTimeLabel(),
    status,
  };
}

function getDisplayStatus(status: RuntimeStatus): string {
  if (status === "thinking") {
    return "Working";
  }

  if (status === "error") {
    return "Needs attention";
  }

  if (status === "success") {
    return "Ready";
  }

  return "Ready";
}

export default function ButtonInterfacePage() {
  const [requestText, setRequestText] = useState("");
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus>("ready");
  const [response, setResponse] = useState<NaturalIntelligenceResponse | null>(
    null,
  );
  const [errorMessage, setErrorMessage] = useState("");
  const [displayName, setDisplayName] = useState(
    intelligenceConfig.fallbackDisplayName,
  );
  const [logs, setLogs] = useState<SystemLogItem[]>([]);

  useEffect(() => {
    let isActive = true;

    setLogs([
      createLog("System initialized", "success"),
      createLog("Data Engine connected", "success"),
      createLog("Intelligence runtime ready", "success"),
    ]);

    void getIntelligenceDefinition(intelligenceConfig.definitionPath)
      .then((definition) => {
        if (!isActive) {
          return;
        }

        const activeName =
          definition.identity?.display_name ||
          definition.identity?.name ||
          intelligenceConfig.fallbackDisplayName;

        setDisplayName(activeName);
      })
      .catch(() => {
        if (isActive) {
          setDisplayName(intelligenceConfig.fallbackDisplayName);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  async function openExternalUrl(url: string) {
    if (!url.trim()) {
      return;
    }

    try {
      await openUrl(url);
      setLogs((current) => [
        createLog("Opened source link", "success"),
        ...current,
      ]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Could not open the source link.";

      setErrorMessage(message);
      setLogs((current) => [
        createLog("Could not open source link", "error"),
        ...current,
      ]);
    }
  }

  async function handleAsk() {
    const cleanRequest = requestText.trim();

    if (!cleanRequest) {
      setRuntimeStatus("error");
      setErrorMessage("Enter a request first.");
      setLogs((current) => [
        createLog("Request rejected: empty input", "error"),
        ...current,
      ]);
      return;
    }

    setRuntimeStatus("thinking");
    setErrorMessage("");
    setLogs((current) => [
      createLog("Request submitted", "info"),
      ...current,
    ]);

    try {
      const result = await processNaturalIntelligenceRequest(
        cleanRequest,
        intelligenceConfig.definitionPath,
      );

      setResponse(result);
      setRuntimeStatus(result.status === "success" ? "success" : "error");

      setLogs((current) => [
        createLog("Response received", "success"),
        ...current,
      ]);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "The request could not be completed.";

      setRuntimeStatus("error");
      setErrorMessage(message);

      setLogs((current) => [
        createLog("Runtime request failed", "error"),
        ...current,
      ]);
    }
  }

  function handleClearLog() {
    setLogs([]);
  }

  return (
    <main className="intelligence-page">
      <section className="intelligence-header">
        <div>
          <p className="eyebrow">Data Platform</p>
          <h1>{intelligenceConfig.pageTitle}</h1>
          <p className="page-subtitle">
            Ask one question. The system handles routing, memory, and response
            generation behind the interface.
          </p>
        </div>

        <div className={`compact-runtime-status status-${runtimeStatus}`}>
          <span className="status-dot" />
          <span>{getDisplayStatus(runtimeStatus)}</span>
        </div>
      </section>

      <section className="metric-grid metric-grid-clean" aria-label="Platform status">
        <article className="metric-card metric-card-clean">
          <div>
            <p>Sources</p>
            <strong>1</strong>
            <small>Connected</small>
          </div>
        </article>

        <article className="metric-card metric-card-clean">
          <div>
            <p>Raw Records</p>
            <strong>1</strong>
            <small>Ready</small>
          </div>
        </article>

        <article className="metric-card metric-card-clean">
          <div>
            <p>Definitions</p>
            <strong>Active</strong>
            <small>Ready</small>
          </div>
        </article>

        <article className="metric-card metric-card-clean">
          <div>
            <p>Validation</p>
            <strong>Enabled</strong>
            <small>Ready</small>
          </div>
        </article>

        <article className="metric-card metric-card-clean">
          <div>
            <p>Runtime</p>
            <strong>Active</strong>
            <small>Ready</small>
          </div>
        </article>
      </section>

      <section className="main-grid">
        <article className="panel ask-panel">
          <h2>Ask</h2>

          <label className="field-label" htmlFor="model-select">
            Model
          </label>

          <select id="model-select" className="model-select" value="ollama" disabled>
            <option value="ollama">{intelligenceConfig.providerLabel}</option>
          </select>

          <label className="field-label" htmlFor="request-input">
            Ask {displayName}
          </label>

          <textarea
            id="request-input"
            className="request-input"
            placeholder={`Ask ${displayName}...`}
            value={requestText}
            onChange={(event) => setRequestText(event.target.value)}
            onKeyDown={(event) => {
              if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                void handleAsk();
              }
            }}
          />

          <div className="ask-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void handleAsk()}
              disabled={runtimeStatus === "thinking"}
            >
              {runtimeStatus === "thinking" ? "Working" : "Ask"}
            </button>
          </div>

          {errorMessage ? (
            <div className="error-box">{errorMessage}</div>
          ) : null}
        </article>

        <article className="panel response-panel">
          <h2>Response</h2>

          {response ? (
            <div className="natural-response natural-response-only">
              <p>{response.answer}</p>

              {response.results.length > 0 ? (
                <section className="result-section">
                  <div className="result-list">
                    {response.results.map((item) => (
                      <article className="result-card" key={item.url}>
                        <strong>{item.title}</strong>
                        <button
                          type="button"
                          className="result-url-button"
                          onClick={() => {
                            void openExternalUrl(item.url);
                          }}
                        >
                          {item.url}
                        </button>

                        <div className="result-actions">
                          <button
                            type="button"
                            className="result-action-button primary-result-action"
                            onClick={() => {
                              void openExternalUrl(item.url);
                            }}
                          >
                            Open page ↗
                          </button>

                          <button
                            type="button"
                            className="result-action-button"
                            onClick={() => {
                              void openExternalUrl(item.url);
                            }}
                          >
                            Learn more
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          ) : (
            <div className="empty-response">
              <div className="empty-icon">◌</div>
              <p>Enter a request to get started.</p>
            </div>
          )}
        </article>
      </section>

      <section className="panel output-panel">
        <div className="output-header">
          <h2>Output / System Log</h2>
          <button type="button" className="ghost-button" onClick={handleClearLog}>
            Clear Log
          </button>
        </div>

        {logs.length > 0 ? (
          <div className="log-list">
            {logs.map((item) => (
              <div className="log-row" key={item.id}>
                <span className={`log-dot log-${item.status}`} />
                <span>{item.message}</span>
                <time>{item.time}</time>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-log">No log entries.</p>
        )}
      </section>
    </main>
  );
}
