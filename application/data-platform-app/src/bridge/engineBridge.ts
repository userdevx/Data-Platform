
import { invoke } from "@tauri-apps/api/core";
import type { DataRecord, EngineStatus } from "../types/appTypes";

export async function getEngineStatus(): Promise<EngineStatus> {
  try {
    return await invoke<EngineStatus>("get_engine_status");
  } catch (error) {
    throw new Error(formatBridgeError(error));
  }
}

export async function getRecentRecords(limit = 25): Promise<DataRecord[]> {
  try {
    return await invoke<DataRecord[]>("get_recent_records", {
      limit
    });
  } catch (error) {
    throw new Error(formatBridgeError(error));
  }
}

export async function queryRecords(
  dataType?: string,
  limit = 25
): Promise<DataRecord[]> {
  try {
    return await invoke<DataRecord[]>("query_records", {
      dataType,
      limit
    });
  } catch (error) {
    throw new Error(formatBridgeError(error));
  }
}

function formatBridgeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "Unknown Engine Bridge error";
}

export type IntelligenceResult = {
  status: string;
  question: string;
  route: string | null;
  source: string | null;
  reason: string | null;
  answer: string;
  matched: boolean | null;
  classification?: Record<string, unknown>;
  insights?: Record<string, unknown>;
};

export async function askIntelligence(question: string): Promise<IntelligenceResult> {
  const cleanQuestion = question.trim();

  if (!cleanQuestion) {
    return {
      status: "error",
      question: "",
      route: "none",
      source: "none",
      reason: "Question was empty.",
      answer: "Enter a request first.",
      matched: false,
    };
  }

  const rawResponse = await invoke<string>("process_intelligence_request", {
    question: cleanQuestion,
  });

  try {
    return JSON.parse(rawResponse) as IntelligenceResult;
  } catch {
    return {
      status: "error",
      question: cleanQuestion,
      route: "parse_error",
      source: "engineBridge",
      reason: "The application received invalid JSON from the Intelligence Runtime.",
      answer: rawResponse,
      matched: false,
    };
  }
}
