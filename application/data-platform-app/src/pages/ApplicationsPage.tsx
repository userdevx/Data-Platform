import {
  useState,
} from "react";

import {
  openPath,
} from "@tauri-apps/plugin-opener";

import {
  generateApplication,
  type GeneratedApplication,
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


  const canBuild =
    request.trim().length > 0
    && !building;


  async function handleBuild(): Promise<void> {
    if (!canBuild) {
      return;
    }

    setBuilding(
      true,
    );

    setBuildError(
      "",
    );

    setResult(
      null,
    );

    try {
      const generated = await generateApplication(request.trim());
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
    }
  }


  return (
    <main className="dw-build-page">
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
                void openPath(
                  result.project_path,
                );
              }}
            >
              Open folder
            </button>
          </section>
        ) : null}


      </section>
    </main>
  );
}
