import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type {
  BuildEvent,
  GeneratedApplication,
} from "../bridge/applicationGenerationBridge";

import "./ApplicationPreview.css";

type Props = {
  building: boolean;
  buildEvents: BuildEvent[];
  result: GeneratedApplication | null;
  buildError: string;
};

type PreviewDocument = {
  html: string;
  project_name: string;
  preview_kind: string;
  engineering_verified: boolean;
};

type Viewport = "desktop" | "mobile";

const previewPolicy =
  `<meta http-equiv="Content-Security-Policy" ` +
  `content="default-src 'none'; ` +
  `script-src 'unsafe-inline'; ` +
  `style-src 'unsafe-inline'; ` +
  `img-src data: blob:; font-src data:; ` +
  `connect-src 'none'; form-action 'none'; ` +
  `base-uri 'none'">`;

function isolatedDocument(html: string): string {
  // Preserve the document type and inject restrictions into <head>.
  if (!/<head(?:\s[^>]*)?>/i.test(html)) {
    return `<!DOCTYPE html><html><head>${previewPolicy}</head>` +
      `<body>${html}</body></html>`;
  }

  return html.replace(
    /<head(?:\s[^>]*)?>/i,
    (head) => head + previewPolicy,
  );
}

export default function ApplicationPreview({
  building,
  buildEvents,
  result,
  buildError,
}: Props) {
  const [preview, setPreview] =
    useState<PreviewDocument | null>(null);

  const [viewport, setViewport] =
    useState<Viewport>("desktop");

  const [loading, setLoading] = useState(false);
  const [documentLoaded, setDocumentLoaded] =
    useState(false);

  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  const projectPath = result?.project_path ?? null;

  useEffect(() => {
    let cancelled = false;

    if (building) {
      setPreview(null);
      setDocumentLoaded(false);
      setError("");
      return;
    }

    if (buildError) {
      setPreview(null);
      setError("The build failed. No new preview is available.");
      return;
    }

    if (!projectPath) {
      setPreview(null);
      setDocumentLoaded(false);
      setLoading(false);
      setError("");
      return;
    }

    setLoading(true);
    setError("");
    setDocumentLoaded(false);
    setPreview(null);

    invoke<PreviewDocument>(
      "read_application_preview",
      { projectPath },
    )
      .then((document) => {
        if (!cancelled) {
          setPreview(document);
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [building, buildError, projectPath, refresh]);

  const html = preview
    ? isolatedDocument(preview.html)
    : null;

  return (
    <aside
      className="dw-application-preview"
      aria-label="Application preview"
    >
      <header className="dw-application-preview__header">
        <div>
          <h2>Application Preview</h2>
          <p>
            {building
              ? "Application building"
              : loading
                ? "Loading generated application"
                : documentLoaded
                  ? "Application preview loaded"
                  : "Preview awaiting application"}
          </p>
        </div>

        <div className="dw-application-preview__controls">
          <button
            type="button"
            className={viewport === "desktop" ? "is-active" : ""}
            aria-pressed={viewport === "desktop"}
            onClick={() => setViewport("desktop")}
          >
            Desktop
          </button>

          <button
            type="button"
            className={viewport === "mobile" ? "is-active" : ""}
            aria-pressed={viewport === "mobile"}
            onClick={() => setViewport("mobile")}
          >
            Mobile
          </button>

          <button
            type="button"
            onClick={() => setRefresh((value) => value + 1)}
            disabled={building}
          >
            Refresh
          </button>
        </div>
      </header>

      <div className="dw-application-preview__body">
        {html && !building ? (
          <div
            className={
              "dw-application-preview__viewport " +
              `is-${viewport}`
            }
          >
            <iframe
              key={`${preview?.project_name}-${refresh}`}
              title="DataWorc generated application preview"
              srcDoc={html}
              sandbox="allow-scripts allow-modals"
              referrerPolicy="no-referrer"
              onLoad={() => setDocumentLoaded(true)}
            />
          </div>
        ) : (
          <div className="dw-application-preview__empty">
            <div className="dw-application-preview__empty-icon">
              ▣
            </div>

            <h3>
              {building
                ? "Building your application"
                : error
                  ? "Preview unavailable"
                  : "Your application will appear here"}
            </h3>

            <p>
              {building
                ? `${buildEvents.length} build events received.`
                : error ||
                  "Generated web applications are displayed automatically."}
            </p>
          </div>
        )}
      </div>

      <footer className="dw-application-preview__footer">
        {preview
          ? `${preview.project_name} · Source preview. ` +
            `Functional and security verification remain separate.`
          : "DataWorc automatically discovers generated HTML applications."}
      </footer>
    </aside>
  );
}
