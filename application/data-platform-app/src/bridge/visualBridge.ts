import { invoke } from "@tauri-apps/api/core";


export type VisualRuntimeStatus =
  | "ready"
  | "disabled"
  | "unavailable"
  | "rejected"
  | "invalid_media"
  | "invalid_observation"
  | "provider_error"
  | "configuration_error"
  | "success"
  | "skipped";


export type VisualBridgeResponse = {
  status: VisualRuntimeStatus | string;
  answer: string;
  data: Record<string, unknown>;
  errors: string[];
};


export type AnalyzeVisualImageRequest = {
  imagePath: string;
  query: string;
  sourceReference?: string;
};


export async function getVisualRuntimeStatus(
): Promise<VisualBridgeResponse> {
  return invoke<VisualBridgeResponse>(
    "get_visual_runtime_status",
  );
}


export async function analyzeVisualImage(
  request: AnalyzeVisualImageRequest,
): Promise<VisualBridgeResponse> {
  return invoke<VisualBridgeResponse>(
    "analyze_visual_image",
    {
      request,
    },
  );
}
