export type AppMode = "user" | "developer";

export type UserModePage =
  | "Dashboard"
  | "Data"
  | "Intelligence"
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
};

export const modeOptions: ModeOption[] = [
  {
    id: "user",
    label: "User Mode",
    description: "Use the Data Platform."
  },
  {
    id: "developer",
    label: "Developer Mode",
    description: "Open development tools."
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
    id: "Intelligence",
    label: "Intelligence",
    description: "Ask questions and review answers."
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
    label: "Command Terminal",
    description: "Run commands, review output, and inspect the Data Platform."
  },
  {
    id: "Git",
    label: "Git",
    description: "Review repository status, branches, and recent commits."
  },
  {
    id: "Build",
    label: "Build",
    description: "Build the application and review build output."
  },
  {
    id: "Tests",
    label: "Tests",
    description: "Run test suites and review results."
  },
  {
    id: "Logs",
    label: "Logs",
    description: "View application, engine, and Intelligence logs."
  },
  {
    id: "Processes",
    label: "Processes",
    description: "Inspect running platform processes."
  },
  {
    id: "Environment",
    label: "Environment",
    description: "View OS, shell, runtime versions, and project paths."
  }
];
