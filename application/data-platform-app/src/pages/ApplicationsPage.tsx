import {
  useState,
} from "react";

import {
  openPath,
} from "@tauri-apps/plugin-opener";

import {
  generateApplication,
  type ApplicationType,
  type GeneratedApplication,
} from "../bridge/applicationGenerationBridge";

import "./ApplicationsPage.css";


const applicationTypes: ApplicationType[] = [
  "Web application",
  "Desktop application",
  "Data application",
  "Automation tool",
];


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
    applicationType,
    setApplicationType,
  ] = useState<ApplicationType>(
    "Desktop application",
  );


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
      const generated =
        await generateApplication(
          request.trim(),
          applicationType,
        );

      setResult(
        generated,
      );
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


        <div
          className="dw-build-types"
          aria-label="Application type"
        >
          {applicationTypes.map((type) => (
            <button
              key={type}
              type="button"
              disabled={building}
              className={
                type === applicationType
                  ? "dw-build-type is-active"
                  : "dw-build-type"
              }
              onClick={() => {
                setApplicationType(
                  type,
                );
              }}
            >
              {type}
            </button>
          ))}
        </div>





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


        <p className="dw-build-runtime-note">
          Build creates a real local starter project.
          Local-model refinement and sandbox
          compile/test are the next generation stage.
        </p>
      </section>
    </main>
  );
}
