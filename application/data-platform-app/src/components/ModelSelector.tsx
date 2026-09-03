import type {
  ModelOption,
} from "../bridge/modelBridge";


export type ModelSelectorProps = {
  modelOptions: ModelOption[];
  modelsLoading: boolean;
  selectedModelId: string;
  runtimeStatus: string;

  onModelChange: (
    value: string,
  ) => void;
};


const USER_MODE_ALLOWED_CAPABILITIES = new Set([
  "text_input",
  "text_generation",
  "image_generation",
  "chat",
  "conversation",
  "reasoning",
]);


const USER_MODE_BLOCKED_CAPABILITIES = new Set([
  "semantic_similarity",
  "feature_extraction",
  "text_classification",
  "embeddings",
  "embedding",
]);


function isUserModeAskModel(
  model: ModelOption,
): boolean {
  if (
    model.option_id === "automatic"
  ) {
    return true;
  }

  if (
    !model.available
  ) {
    return false;
  }

  const capabilities =
    model.capabilities || [];

  const hasBlockedCapability =
    capabilities.some((capability) =>
      USER_MODE_BLOCKED_CAPABILITIES.has(
        capability,
      ),
    );

  if (
    hasBlockedCapability
  ) {
    return false;
  }

  const hasAllowedCapability =
    capabilities.some((capability) =>
      USER_MODE_ALLOWED_CAPABILITIES.has(
        capability,
      ),
    );

  return hasAllowedCapability;
}


function getModelLabel(
  model: ModelOption,
): string {
  if (
    model.option_id === "automatic"
  ) {
    return "Automatic";
  }

  return (
    model.display_name
    || model.model_id
    || model.option_id
  );
}


export default function ModelSelector({
  modelOptions,
  modelsLoading,
  selectedModelId,
  runtimeStatus,
  onModelChange,
}: ModelSelectorProps) {
  const visibleModelOptions =
    modelOptions.filter(
      isUserModeAskModel,
    );

  return (
    <>
      <label
        className="field-label"
        htmlFor="model-select"
      >
        Model
      </label>

      <select
        id="model-select"
        className="model-select"
        value={
          selectedModelId
        }
        disabled={
          modelsLoading
          || runtimeStatus === "thinking"
        }
        onChange={(event) => {
          onModelChange(
            event.target.value,
          );
        }}
      >
        {modelsLoading ? (
          <option value="">
            Loading models…
          </option>
        ) : null}

        {!modelsLoading
          && visibleModelOptions.length === 0 ? (
            <option value="">
              No Ask models available
            </option>
          ) : null}

        {!modelsLoading
          ? visibleModelOptions.map(
              (model) => (
                <option
                  key={
                    model.option_id
                  }
                  value={
                    model.option_id
                  }
                  disabled={
                    !model.available
                  }
                >
                  {getModelLabel(
                    model,
                  )}
                  {model.available
                    ? ""
                    : " — Unavailable"}
                </option>
              ),
            )
          : null}
      </select>
    </>
  );
}
