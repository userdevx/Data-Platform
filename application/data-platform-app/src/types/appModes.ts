export type AppMode = "user" | "developer";

export type UserModePage =
  | "Dashboard"
  | "Data"
  | "Paige"
  | "Queries"
  | "Pipelines"
  | "Settings";

export type DeveloperModePage =
  | "Terminal"
  | "Git"
  | "Build"
  | "Tests"
  | "Logs"
  | "Processes"
  | "Environment";

export type ModeOption = {
  id: AppMode;
  label: string;
  description: string;
};

export type UserNavigationItem = {
  id: UserModePage;
  label: string;
  description: string;
};

export type DeveloperNavigationItem = {
  id: DeveloperModePage;
  label: string;
  description: string;
  status: "Ready" | "Planned";
};

export const modeOptions: ModeOption[] = [
  {
    id: "user",
    label: "User Mode",
    description: "Use the Data Platform application."
  },
  {
    id: "developer",
    label: "Developer Mode",
    description: "Build, test, debug, and inspect the platform."
  }
];

export const userModeNavigation: UserNavigationItem[] = [
  {
    id: "Dashboard",
    label: "Dashboard",
    description: "View platform metrics, records, quality, and storage."
  },
  {
    id: "Data",
    label: "Data",
    description: "Connect files and create Data Engine databases."
  },
  {
    id: "Paige",
    label: "Paige",
    description: "Ask questions and review source-backed answers."
  },
  {
    id: "Queries",
    label: "Queries",
    description: "Run queries against stored records."
  },
  {
    id: "Pipelines",
    label: "Pipelines",
    description: "Process records through pipeline stages."
  },
  {
    id: "Settings",
    label: "Settings",
    description: "Manage application preferences."
  }
];

export const developerModeNavigation: DeveloperNavigationItem[] = [
  {
    id: "Terminal",
    label: "Terminal",
    description: "Run project commands in a developer workspace.",
    status: "Planned"
  },
  {
    id: "Git",
    label: "Git",
    description: "Review repository status, commits, and changes.",
    status: "Planned"
  },
  {
    id: "Build",
    label: "Build",
    description: "Run frontend, backend, Rust, and packaging checks.",
    status: "Planned"
  },
  {
    id: "Tests",
    label: "Tests",
    description: "Run backend and application tests.",
    status: "Planned"
  },
  {
    id: "Logs",
    label: "Logs",
    description: "View application, system, and Paige logs.",
    status: "Planned"
  },
  {
    id: "Processes",
    label: "Processes",
    description: "Inspect running platform and worker processes.",
    status: "Planned"
  },
  {
    id: "Environment",
    label: "Environment",
    description: "View detected OS, shell, runtimes, and paths.",
    status: "Planned"
  }
];
