export type AppMode = "developer" | "user";

export type DeveloperPage =
  | "home"
  | "ingestion"
  | "lakehouse"
  | "processing"
  | "query"
  | "analytics"
  | "monitoring"
  | "jobs"
  | "settings";

export type UserPage =
  | "home"
  | "analytics"
  | "query"
  | "reports"
  | "monitoring"
  | "settings";

export type AppPage = DeveloperPage | UserPage;

export type DataRecord = {
  id: string;
  source: string;
  category: string;
  sensor_type: string;
  value: string | number | boolean | null | Record<string, unknown>;
  unit: string;
  timestamp: string;
  metadata?: Record<string, unknown> | null;
};

export type EngineStatus = {
  status: string;
  record_count: number;
  records_path: string;
};
