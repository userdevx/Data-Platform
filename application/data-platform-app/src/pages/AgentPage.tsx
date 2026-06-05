import { invoke } from "@tauri-apps/api/core";
import { useState } from "react";
import "./AgentPage.css";

type AgentPageProps = {
  onBackToWorkspace: () => void;
};

type AgentOutput = {
  source?: string;
  category?: string;
  record_type?: string;
  input?: string;
  action?: string;
  result?: string;
  unit?: string;
  timestamp?: string;
  agent_name?: string;
  status?: string;
};

function getResultMessage(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  if (
    value &&
    typeof value === "object" &&
    "message" in value &&
    typeof value.message === "string"
  ) {
    return value.message;
  }

  return "Done.";
}

function AgentPage({ onBackToWorkspace }: AgentPageProps) {
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [output, setOutput] = useState<AgentOutput | null>(null);
  const [activityLog, setActivityLog] = useState("");
  const [status, setStatus] = useState("Paige is ready.");
  const [isRunning, setIsRunning] = useState(false);

  async function startPaige() {
    try {
      setStatus("Starting Paige...");

      const result = await invoke<unknown>("start_agent_worker");

      setStatus(getResultMessage(result));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  }

  async function askQuestion() {
    const cleanQuestion = question.trim();

    if (!cleanQuestion) {
      setStatus("Type a question first.");
      return;
    }

    try {
      setIsRunning(true);
      setOutput(null);
      setActivityLog("");
      setSubmittedQuestion(cleanQuestion);
      setStatus("Sending your question...");

      const submitResult = await invoke<unknown>("submit_agent_task", {
        input: cleanQuestion
      });

      setStatus(`${getResultMessage(submitResult)} Looking for an answer...`);

      await pollForOutput(cleanQuestion);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setIsRunning(false);
    }
  }

  async function pollForOutput(expectedInput: string) {
    const maxAttempts = 20;
    const waitMs = 1000;

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        setStatus(`Working on it... ${attempt}/${maxAttempts}`);

        const raw = await invoke<string>("read_agent_output");
        const parsed = JSON.parse(raw) as AgentOutput;

        const outputMatchesQuestion =
          parsed.input?.trim().toLowerCase() === expectedInput.trim().toLowerCase();

        const outputIsComplete =
          parsed.status === "complete" || parsed.status === "error";

        if (outputMatchesQuestion && outputIsComplete) {
          setOutput(parsed);
          setStatus(
            parsed.status === "complete"
              ? "Answer ready."
              : "Something went wrong. Review the message below."
          );
          setQuestion("");
          return;
        }
      } catch {
        // The output file may not exist yet. Keep checking.
      }

      await new Promise((resolve) => window.setTimeout(resolve, waitMs));
    }

    setStatus(
      "No new answer appeared yet. Try Read Latest Answer or check the activity log."
    );
  }

  async function readLatestOutput() {
    try {
      setStatus("Reading latest answer...");

      const raw = await invoke<string>("read_agent_output");
      const parsed = JSON.parse(raw) as AgentOutput;

      setOutput(parsed);
      setStatus("Latest answer loaded.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  }

  async function readActivityLog() {
    try {
      setStatus("Reading activity log...");

      const log = await invoke<string>("read_agent_log");

      setActivityLog(log);
      setStatus("Activity log loaded.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error));
    }
  }

  function submitOnEnter(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      void askQuestion();
    }
  }

  return (
    <main className="agent-page">
      <section className="agent-header">
        <div>
          <p className="agent-eyebrow">Intelligence Layer</p>
          <h1>Paige</h1>
          <p>
            Ask a question and Paige will return a useful answer with sources
            when available.
          </p>
        </div>

        <div className="agent-header-actions">
          <div className="agent-status-card">
            <span className="agent-status-dot"></span>
            Paige is available
          </div>

          <button
            type="button"
            className="agent-back-button"
            onClick={onBackToWorkspace}
          >
            Back to Workspace
          </button>
        </div>
      </section>

      <section className="agent-grid">
        <article className="agent-panel agent-main-panel">
          <h2>Ask Paige</h2>

          <div className="agent-input-row">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={submitOnEnter}
              placeholder="Ask a question..."
            />

            <button type="button" onClick={askQuestion} disabled={isRunning}>
              {isRunning ? "Searching..." : "Ask Question"}
            </button>
          </div>

          <p className="agent-status-line">{status}</p>

          {submittedQuestion ? (
            <p className="agent-status-line">
              Last question: <strong>{submittedQuestion}</strong>
            </p>
          ) : null}

          <div className="agent-button-row">
            <button type="button" onClick={startPaige}>
              Start Paige
            </button>

            <button type="button" onClick={readLatestOutput}>
              Read Latest Answer
            </button>

            <button type="button" onClick={readActivityLog}>
              View Activity Log
            </button>
          </div>

          {output ? (
            <section className="agent-output-card">
              <h2>Answer</h2>

              <div className="agent-output-grid">
                <span>Question</span>
                <strong>{output.input || "—"}</strong>

                <span>Action</span>
                <strong>{output.action || "—"}</strong>

                <span>Status</span>
                <strong>{output.status || "—"}</strong>

                <span>Name</span>
                <strong>Paige</strong>

                <span>Time</span>
                <strong>{output.timestamp || "—"}</strong>
              </div>

              <div className="agent-result">
                <strong>Result</strong>
                <p>{output.result || "No answer returned yet."}</p>
              </div>
            </section>
          ) : (
            <section className="agent-output-card">
              <h2>Answer</h2>
              <p>No answer loaded yet. Ask a question or read the latest answer.</p>
            </section>
          )}

          {activityLog ? (
            <section className="agent-output-card">
              <h2>Activity Log</h2>
              <pre className="agent-log">{activityLog}</pre>
            </section>
          ) : null}
        </article>

        <article className="agent-panel">
          <h2>Files</h2>

          <div className="agent-tool-row">
            <span>agent_worker.py</span>
            <small>Worker</small>
          </div>

          <div className="agent-tool-row">
            <span>agent_input.json</span>
            <small>Question</small>
          </div>

          <div className="agent-tool-row">
            <span>agent_output.json</span>
            <small>Answer</small>
          </div>

          <div className="agent-tool-row">
            <span>agent.log</span>
            <small>Activity</small>
          </div>
        </article>

        <article className="agent-panel">
          <h2>Flow</h2>

          <ol className="agent-flow">
            <li>User asks a question</li>
            <li>The question is saved</li>
            <li>Paige reads the question</li>
            <li>Paige searches or processes the request</li>
            <li>The answer is saved</li>
            <li>The interface reads the latest answer</li>
            <li>The answer appears on screen</li>
          </ol>
        </article>
      </section>
    </main>
  );
}

export default AgentPage;
