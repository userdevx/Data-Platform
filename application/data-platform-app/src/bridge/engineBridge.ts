
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
  sensorType?: string,
  limit = 25
): Promise<DataRecord[]> {
  try {
    return await invoke<DataRecord[]>("query_records", {
      sensorType,
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
