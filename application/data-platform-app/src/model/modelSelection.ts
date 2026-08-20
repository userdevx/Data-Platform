import type {
  ModelOption,
} from "../bridge/modelBridge";


export function isAutomaticModel(
  model: ModelOption | null,
): boolean {
  return (
    model?.option_id === "automatic"
  );
}
