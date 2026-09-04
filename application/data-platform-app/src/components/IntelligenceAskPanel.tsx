import type {
  ModelOption,
} from "../bridge/modelBridge";

import ModelSelector from "./ModelSelector";
import RequestComposer from "./RequestComposer";


export type IntelligenceAskPanelProps = {
  displayName: string;

  modelOptions: ModelOption[];
  modelsLoading: boolean;

  selectedModelId: string;
  selectedModel: ModelOption | null;

  requestText: string;
  attachmentPaths: string[];

  runtimeStatus: string;
  errorMessage: string;

  onModelChange: (
    value: string,
  ) => void;

  onRequestChange: (
    value: string,
  ) => void;

  onAttachmentChange: (
    value: string[],
  ) => void;

  onAsk: () => void;
  onCancel: () => void;
};


export default function IntelligenceAskPanel({
  displayName,
  modelOptions,
  modelsLoading,
  selectedModelId,
  selectedModel,
  requestText,
  attachmentPaths,
  runtimeStatus,
  errorMessage,
  onModelChange,
  onRequestChange,
  onAttachmentChange,
  onAsk,
  onCancel,
}: IntelligenceAskPanelProps) {
  return (
    <article className="panel ask-panel">
      <h2>Ask</h2>

      <ModelSelector
        modelOptions={modelOptions}
        modelsLoading={modelsLoading}
        selectedModelId={
          selectedModelId
        }
        runtimeStatus={
          runtimeStatus
        }
        onModelChange={
          onModelChange
        }
      />

      <RequestComposer
        displayName={displayName}
        requestText={requestText}
        attachmentPaths={
          attachmentPaths
        }
        runtimeStatus={
          runtimeStatus
        }
        onRequestChange={
          onRequestChange
        }
        onAttachmentChange={
          onAttachmentChange
        }
        onAsk={onAsk}
      />

      <div className="ask-actions">
        <button
          type="button"
          className="primary-button"
          onClick={
            runtimeStatus === "thinking"
              ? onCancel
              : onAsk
          }
          disabled={
            modelsLoading
            || !selectedModel
          }
        >
          {runtimeStatus === "thinking"
            ? "Cancel"
            : "Ask"}
        </button>
      </div>

      {errorMessage ? (
        <div
          className="error-box"
          role="alert"
        >
          {errorMessage}
        </div>
      ) : null}
    </article>
  );
}
