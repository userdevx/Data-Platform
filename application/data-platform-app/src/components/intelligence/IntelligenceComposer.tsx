import { useState, type KeyboardEvent } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import type { ModelOption } from "../../bridge/modelBridge";
import "./composer.css";

export type IntelligenceComposerProps = {
  modelOptions: ModelOption[];
  modelsLoading: boolean;
  selectedModelId: string | null;
  requestText: string;
  attachmentPaths: string[];
  busy: boolean;
  errorMessage: string;
  onModelChange: (modelId: string) => void;
  onRequestChange: (text: string) => void;
  onAttachmentChange: (paths: string[]) => void;
  onSend: () => void;
  onCancel: () => void;
};

function fileName(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

export default function IntelligenceComposer({
  modelOptions,
  modelsLoading,
  selectedModelId,
  requestText,
  attachmentPaths,
  busy,
  errorMessage,
  onModelChange,
  onRequestChange,
  onAttachmentChange,
  onSend,
  onCancel,
}: IntelligenceComposerProps) {
  const [pickerError, setPickerError] = useState("");
  const canSend = !busy && requestText.trim().length > 0;

  async function pickFiles(): Promise<void> {
    setPickerError("");
    try {
      const picked = await open({ multiple: true });
      if (!picked) {
        return;
      }
      const list = (Array.isArray(picked) ? picked : [picked]).map(String);
      onAttachmentChange(Array.from(new Set([...attachmentPaths, ...list])));
    } catch (error) {
      setPickerError(
        error instanceof Error ? error.message : "Files could not be selected.",
      );
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (canSend) {
        onSend();
      }
    }
  }

  const message = errorMessage || pickerError;

  return (
    <form
      className="dw-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSend) {
          onSend();
        }
      }}
    >
      <textarea
        className="dw-composer__input"
        aria-label="Your question"
        placeholder="Ask a question or describe a task…"
        rows={3}
        value={requestText}
        onChange={(event) => onRequestChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />

      {attachmentPaths.length > 0 ? (
        <ul className="dw-chips" aria-label="Attached files">
          {attachmentPaths.map((path) => (
            <li key={path} className="dw-chip" title={path}>
              <span>{fileName(path)}</span>
              <button
                type="button"
                className="dw-chip__remove"
                aria-label={`Remove ${fileName(path)}`}
                onClick={() => onAttachmentChange(attachmentPaths.filter((item) => item !== path))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="dw-composer__bar">
        <div className="dw-composer__tools">
          <button
            type="button"
            className="dw-icon-btn"
            aria-label="Attach files"
            disabled={busy}
            onClick={() => {
              void pickFiles();
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>

          <select
            className="dw-select"
            aria-label="Model"
            value={selectedModelId ?? ""}
            disabled={modelsLoading || busy}
            onChange={(event) => onModelChange(event.target.value)}
          >
            {modelsLoading ? <option value="">Loading models…</option> : null}
            {modelOptions.map((model) => (
              <option key={model.option_id} value={model.option_id} disabled={!model.available}>
                {model.display_name}
              </option>
            ))}
          </select>
        </div>

        {busy ? (
          <button type="button" className="dw-btn-secondary" onClick={onCancel}>
            Cancel
          </button>
        ) : (
          <button type="submit" className="dw-btn-primary" disabled={!canSend}>
            Send
          </button>
        )}
      </div>

      {message ? (
        <p className="dw-composer__error" role="alert">
          {message}
        </p>
      ) : null}
    </form>
  );
}
