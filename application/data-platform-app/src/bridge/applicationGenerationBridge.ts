import { Channel } from "@tauri-apps/api/core";
import {
  invoke,
} from "@tauri-apps/api/core";


export type ApplicationType =
  | "Web application"
  | "Desktop application"
  | "Data application"
  | "Automation tool";


export type BuildPhaseStatus =
  | "pending"
  | "running"
  | "success"
  | "error";


export type BuildPhase = {
  id: string;
  label: string;
  status: BuildPhaseStatus;
  detail: string;
};


export type GeneratedApplication = {
  success: boolean;

  project_name: string;
  project_path: string;

  application_type: string;

  files: string[];

  message: string;

  phases: BuildPhase[];

  build_output: string;
  test_output: string;

  preview_path:
    | string
    | null;
};


export type BuildEvent = {
  session_id: string;
  sequence: number;
  kind: string;
  timestamp: string;
  details: Record<string, unknown>;
};

export async function generateApplication(
  request: string,
  onProgress?: (event: BuildEvent) => void,
): Promise<GeneratedApplication> {
  if (!onProgress) {
    return invoke<GeneratedApplication>(
      "start_application_build_bridge",
      { request },
    );
  }

  const sessionId = crypto.randomUUID();
  const onEvent = new Channel<BuildEvent>();

  onEvent.onmessage = (event) => {
    if (event.session_id === sessionId) {
      onProgress(event);
    }
  };

  return invoke<GeneratedApplication>(
    "start_application_build_stream",
    { request, sessionId, onEvent },
  );
}
