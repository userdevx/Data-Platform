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


function getModelLabel(
  model: ModelOption,
): string {
  if (
    model.option_id === "automatic"
  ) {
    return "Automatic";
  }

  return (
    model.model_id
    || model.display_name
  );
}


export default function ModelSelector({
  modelOptions,
  modelsLoading,
  selectedModelId,
  runtimeStatus,
  onModelChange,
}: ModelSelectorProps) {
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
          && modelOptions.length === 0 ? (
            <option value="">
              No models available
            </option>
          ) : null}

        {!modelsLoading
          ? modelOptions.map(
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
