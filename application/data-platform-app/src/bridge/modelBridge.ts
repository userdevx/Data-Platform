import { invoke } from "@tauri-apps/api/core";

import type {
  NaturalIntelligenceResponse,
} from "./intelligenceBridge";


export type ModelOption = {
  option_id: string;
  provider_id: string;
  model_id: string;
  display_name: string;
  processing_location:
    | "automatic"
    | "local"
    | "private_remote"
    | "cloud";
  available: boolean;
  capabilities: string[];
};


export type ModelOptionsResponse = {
  status: "success" | "error";
  models: ModelOption[];
  errors: string[];
};


function normalizeBridgeError(
  error: unknown,
): Error {
  if (error instanceof Error) {
    return error;
  }

  if (typeof error === "string") {
    try {
      const parsed = JSON.parse(
        error,
      ) as {
        errors?: unknown;
        message?: unknown;
      };

      if (
        Array.isArray(parsed.errors)
        && typeof parsed.errors[0]
          === "string"
      ) {
        return new Error(
          parsed.errors[0],
        );
      }

      if (
        typeof parsed.message === "string"
      ) {
        return new Error(
          parsed.message,
        );
      }
    } catch {
      return new Error(error);
    }

    return new Error(error);
  }

  return new Error(
    "The model bridge request failed.",
  );
}


function parseJsonResponse<T>(
  raw: string,
): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new Error(
      "The backend returned an invalid JSON response.",
    );
  }
}


export async function getModelOptions():
  Promise<ModelOptionsResponse> {
  try {
    const raw = await invoke<string>(
      "get_model_options",
    );

    const result =
      parseJsonResponse<ModelOptionsResponse>(
        raw,
      );

    if (
      result.status !== "success"
      && result.status !== "error"
    ) {
      throw new Error(
        "The model-options response has an invalid status.",
      );
    }

    if (!Array.isArray(result.models)) {
      throw new Error(
        "The model-options response contains an invalid model list.",
      );
    }

    return result;
  } catch (error) {
    throw normalizeBridgeError(error);
  }
}


export async function processManualModelRequest(
  question: string,
  optionId: string,
  capability: string = "",
  requestArguments: Record<string, unknown> = {},
  requestId: string = "",
): Promise<NaturalIntelligenceResponse> {
  try {
    const raw = await invoke<string>(
      "process_manual_model_request",
      {
        question,
        optionId,
        capability,
        argumentsJson: JSON.stringify(
          requestArguments,
        ),
        requestId,
      },
    );

    const result =
      parseJsonResponse<NaturalIntelligenceResponse>(
        raw,
      );

    if (
      result.status !== "success"
      && result.status !== "error"
    ) {
      throw new Error(
        "The model response has an invalid status.",
      );
    }

    if (typeof result.answer !== "string") {
      throw new Error(
        "The model response contains an invalid answer.",
      );
    }

    if (!Array.isArray(result.results)) {
      throw new Error(
        "The model response contains an invalid result list.",
      );
    }

    return result;
  } catch (error) {
    throw normalizeBridgeError(error);
  }
}


export async function cancelManualModelRequest(
  requestId: string,
): Promise<string> {
  try {
    return await invoke<string>(
      "cancel_manual_model_request",
      {
        requestId,
      },
    );
  } catch (error) {
    throw normalizeBridgeError(error);
  }
}
