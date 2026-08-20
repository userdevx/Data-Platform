import {
  useMemo,
  useState,
} from "react";

import type {
  ModelOption,
} from "../bridge/modelBridge";


export type ModelSelectionState = {
  selectedModelId: string;

  setSelectedModelId: (
    value: string,
  ) => void;

  selectedModel: ModelOption | null;
};


function findSelectedModel(
  models: readonly ModelOption[],
  selectedModelId: string,
): ModelOption | null {
  return (
    models.find(
      (model) =>
        model.option_id
        === selectedModelId,
    )
    ?? null
  );
}


export function useModelSelection(
  models: readonly ModelOption[],
): ModelSelectionState {
  const [
    selectedModelId,
    setSelectedModelId,
  ] = useState("");

  const selectedModel = useMemo(
    () =>
      findSelectedModel(
        models,
        selectedModelId,
      ),
    [
      models,
      selectedModelId,
    ],
  );

  return {
    selectedModelId,
    setSelectedModelId,
    selectedModel,
  };
}
