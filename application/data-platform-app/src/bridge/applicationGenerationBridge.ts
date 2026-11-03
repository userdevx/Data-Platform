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


export async function generateApplication(
  request: string,
): Promise<GeneratedApplication> {
  return invoke<GeneratedApplication>(
    "start_application_build_bridge",
    {
      request,
    },
  );
}
