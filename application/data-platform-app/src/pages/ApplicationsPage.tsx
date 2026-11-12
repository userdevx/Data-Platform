import ApplicationPreview from "./ApplicationPreview";
import {
  useState,
} from "react";

import {
  openPath,
} from "@tauri-apps/plugin-opener";

import {
  generateApplication,
  type GeneratedApplication,
  type BuildEvent,
} from "../bridge/applicationGenerationBridge";

import "./ApplicationsPage.css";


function errorText(
  error: unknown,
): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "The application could not be generated.";
}


export default function ApplicationsPage() {
  const [
    request,
    setRequest,
  ] = useState("");


  const [
    building,
    setBuilding,
  ] = useState(false);


  const [
    buildError,
    setBuildError,
  ] = useState("");


  const [
    result,
    setResult,
  ] =
    useState<GeneratedApplication | null>(
      null,
    );


  const [buildEvents, setBuildEvents] =
    useState<BuildEvent[]>([]);

  const [buildWorkspaceOpen, setBuildWorkspaceOpen] = useState(false);

  function returnToRequest(): void {
    setBuildWorkspaceOpen(false);
    setResult(null);
    setBuildEvents([]);
    setBuildError("");
  }

  const canBuild =
    request.trim().length > 0
    && !building;


  async function handleBuild(): Promise<void> {
    if (!canBuild) {
      return;
    }

    setBuildWorkspaceOpen(true);

    setBuilding(
      true,
    );

    setBuildError(
      "",
    );

    setResult(
      null,
    );

    setBuildEvents([]);

    try {
      const generated = await generateApplication(
        request.trim(),
        (event) => {
          setBuildEvents((previous) =>
            [...previous, event].slice(-150)
          );
        },
      );
      setResult(generated);
    } catch (error) {
      setBuildError(
        errorText(
          error,
        ),
      );
    } finally {
      setBuilding(
        false,
      );
      setBuildWorkspaceOpen(false);
    }
  }


  return (
    <div className={buildWorkspaceOpen ? "dw-builder-split-layout" : undefined}>
<main className="dw-build-page">
      {buildWorkspaceOpen && !building && (
        <div style={{
          display: "flex",
          justifyContent: "flex-end",
          padding: "12px 16px",
        }}>
          <button
            type="button"
            onClick={returnToRequest}
            className="dw-build-open-button"
          >
            New Request
          </button>
        </div>
      )}

      <section
        className="dw-build-page__content"
        aria-labelledby="dw-build-title"
      >
        <header className="dw-build-page__header">
          <h1 id="dw-build-title">
            What would you like to build?
          </h1>

          <p>
            Describe the application you want to create.
          </p>
        </header>


        <section
          className="dw-build-composer"
          aria-label="Application requirements"
        >
          <textarea
            value={request}
            rows={5}
            disabled={building}
            aria-label="Describe your application"
            placeholder="Describe the application, users, features, data, and behavior you need…"
            onChange={(event) => {
              setRequest(
                event.target.value,
              );
            }}
          />


          <div className="dw-build-composer__footer">
            <div className="dw-build-composer__tools">
              <button
                type="button"
                className="dw-build-icon-button"
                disabled
                aria-label="Add application context"
                title="Application attachments will be connected in a later generation stage."
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  aria-hidden="true"
                >
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </button>


              <select
                className="dw-build-model"
                aria-label="Application generation model"
                value="automatic"
                disabled
                onChange={() => {}}
              >
                <option value="automatic">
                  Automatic
                </option>
              </select>
            </div>


            <button
              type="button"
              className="dw-build-button"
              disabled={!canBuild}
              onClick={() => {
                void handleBuild();
              }}
            >
              {building
                ? "Building…"
                : "Build"}
            </button>
          </div>
        </section>







        {buildError ? (
          <section
            className="dw-build-result dw-build-result--error"
            role="alert"
          >
            <strong>
              Build failed
            </strong>

            <p>
              {buildError}
            </p>
          </section>
        ) : null}


        {result?.phases?.length ? (
          <section
            className="dw-build-pipeline"
            aria-label="Application build progress"
          >
            <div className="dw-build-pipeline__header">
              <strong>
                Build pipeline
              </strong>

              <span>
                Verified locally
              </span>
            </div>

            <div className="dw-build-pipeline__steps">
              {result.phases.map((phase) => (
                <div
                  key={phase.id}
                  className={
                    `dw-build-phase is-${phase.status}`
                  }
                >
                  <span
                    className="dw-build-phase__indicator"
                    aria-hidden="true"
                  >
                    {phase.status === "success"
                      ? "✓"
                      : phase.status === "error"
                        ? "!"
                        : phase.status === "running"
                          ? "•"
                          : "○"}
                  </span>

                  <div>
                    <strong>
                      {phase.label}
                    </strong>

                    <p>
                      {phase.detail}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}


        {result ? (
          <section
            className="dw-build-result"
            role="status"
          >
            <div className="dw-build-result__copy">
              <strong>
                Application generated
              </strong>

              <p>
                {result.project_name}
              </p>

              <code>
                {result.project_path}
              </code>

              <span>
                {result.files.length}
                {" "}
                files created
              </span>
            </div>


            <button
              type="button"
              className="dw-build-open-button"
              onClick={() => {
                void openPath(result.project_path).catch((err) => {
                  console.error('Could not open folder:', err);
                });
              }}
            >
              Open folder
            </button>
          </section>
        ) : null}


      </section>
      {(building || buildEvents.length > 0) && (
        <section
          aria-label="Live build activity"
          style={{
            margin: "12px",
            padding: "12px",
            border: "1px solid var(--border-color, #777)",
            borderRadius: "8px",
          }}
        >
          <h2 style={{ fontSize: "1rem" }}>
            Live build activity
          </h2>

          <ol aria-live="polite">
            {buildEvents.map((event) => (
              <li
                key={`${event.session_id}-${event.sequence}`}
              >
                {event.kind.split("_").join(" ")}

                {typeof event.details.path === "string"
                  ? ` · ${event.details.path}`
                  : ""}

                {typeof event.details.stage === "string"
                  ? ` · ${event.details.stage}`
                  : ""}

                {event.details.success === true
                  ? " · passed"
                  : ""}

                {event.details.success === false
                  ? " · failed"
                  : ""}
              </li>
            ))}

            {building && buildEvents.length === 0 && (
              <li>
                Waiting for actual Builder activity…
              </li>
            )}
          </ol>

          <p>
            Source validation is separate from
            functional testing and preview.
          </p>
        </section>
      )}
    </main>
      {buildWorkspaceOpen && (
      <ApplicationPreview
        building={building}
        buildEvents={buildEvents}
        result={result}
        buildError={buildError}
      />
      )}
    </div>
  );
}
