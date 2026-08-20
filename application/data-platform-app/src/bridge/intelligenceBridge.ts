import { invoke } from "@tauri-apps/api/core";

export type IntelligenceDefinitionIdentity = {
  id?: string;
  name?: string;
  display_name?: string;
  role?: string;
  description?: string;
};

export type IntelligenceDefinition = {
  version?: string;
  identity?: IntelligenceDefinitionIdentity;
  memory?: {
    enabled?: boolean;
    source?: string;
    storage_owner?: string;
  };
};

export type IntelligenceSearchResult = {
  title: string;
  url: string;
  source?: string;
  score?: number;
};

export type IntelligenceResponse = {
  response_id?: string;
  request_id?: string;
  created_at?: string;
  instance_id?: string;
  instance_name?: string;
  instance_role?: string;
  ability?: string;
  capability?: string;
  source?: string;
  status?: string;
  answer?: string;
  data?: Record<string, unknown>;
  errors?: string[];
};

export type NaturalIntelligenceResponse = {
  answer: string;
  status: string;
  results: IntelligenceSearchResult[];
  raw: IntelligenceResponse;
};

export const DEFAULT_INTELLIGENCE_DEFINITION =
  "config/intelligence/active.json";

function cleanAnswer(value: unknown): string {
  if (typeof value !== "string") {
    return "No response returned.";
  }

  let answer = value.trim();

  answer = answer.replace(/^Answer:\s*/i, "").trim();

  const sectionMarkers = [
    "\nAction:",
    "\nExplanation:",
    "\nNext Step:",
    "\nNext step:",
    "\nData:",
    "\nMetadata:",
  ];

  for (const marker of sectionMarkers) {
    const markerIndex = answer.indexOf(marker);

    if (markerIndex >= 0) {
      answer = answer.slice(0, markerIndex).trim();
    }
  }

  return answer || "No response returned.";
}

function getString(value: unknown, fallback = ""): string {
  if (typeof value !== "string") {
    return fallback;
  }

  const cleaned = value.trim();
  return cleaned || fallback;
}

function getNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  return undefined;
}

function getSearchResults(value: unknown): IntelligenceSearchResult[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Record<string, unknown> => {
      return typeof item === "object" && item !== null;
    })
    .map((item) => ({
      title: getString(item.title, "Untitled result"),
      url: getString(item.url),
      source: getString(item.source),
      score: getNumber(item.score),
    }))
    .filter((item) => item.url);
}

export async function processIntelligenceRequest(
  question: string,
  definition: string = DEFAULT_INTELLIGENCE_DEFINITION,
): Promise<IntelligenceResponse> {
  const raw = await invoke<string>("process_intelligence_request", {
    question,
    definition,
  });

  return JSON.parse(raw) as IntelligenceResponse;
}

export async function processNaturalIntelligenceRequest(
  question: string,
  definition: string = DEFAULT_INTELLIGENCE_DEFINITION,
): Promise<NaturalIntelligenceResponse> {
  const response = await processIntelligenceRequest(question, definition);

  return {
    answer: cleanAnswer(response.answer),
    status: response.status || "unknown",
    results: getSearchResults(response.data?.results),
    raw: response,
  };
}

export async function getIntelligenceDefinition(
  definition: string = DEFAULT_INTELLIGENCE_DEFINITION,
): Promise<IntelligenceDefinition> {
  const raw = await invoke<string>("get_intelligence_definition", {
    definition,
  });

  return JSON.parse(raw) as IntelligenceDefinition;
}

export async function getApplicationRoot(): Promise<string> {
  return invoke<string>("get_application_root");
}

export type MemorySettings = {
  enabled: boolean;
  read: boolean;
  write: boolean;
  automatic_recall: boolean;
};

export async function updateMemorySettings(
  settings: MemorySettings,
  definition: string = DEFAULT_INTELLIGENCE_DEFINITION,
): Promise<MemorySettings> {
  const raw = await invoke<string>(
    "update_memory_settings",
    {
      definition,
      enabled: settings.enabled,
      read: settings.read,
      write: settings.write,
      automaticRecall:
        settings.automatic_recall,
    },
  );

  const payload = JSON.parse(raw) as {
    status?: string;
    memory?: MemorySettings;
  };

  if (
    payload.status !== "success"
    || !payload.memory
  ) {
    throw new Error(
      "Memory settings could not be updated.",
    );
  }

  return payload.memory;
}

export type PersonalizationSettings = {
  display_name: string;
  role: string;
  description: string;
};

export async function updatePersonalizationSettings(
  settings: PersonalizationSettings,
  definition: string = DEFAULT_INTELLIGENCE_DEFINITION,
): Promise<PersonalizationSettings> {
  const raw = await invoke<string>(
    "update_personalization_settings",
    {
      definition,
      displayName: settings.display_name,
      role: settings.role,
      description: settings.description,
    },
  );

  const payload = JSON.parse(raw) as {
    status?: string;
    personalization?: PersonalizationSettings;
  };

  if (
    payload.status !== "success"
    || !payload.personalization
  ) {
    throw new Error(
      "Personalization settings could not be updated.",
    );
  }

  return payload.personalization;
}

export type PermissionSettings = {
  read_records: boolean;
  write_records: boolean;
  write_history: boolean;
  run_approved_commands: boolean;
  network_access: boolean;
  modify_system_files: boolean;
};

export async function updatePermissionSettings(
  settings: PermissionSettings,
  definition: string = DEFAULT_INTELLIGENCE_DEFINITION,
): Promise<PermissionSettings> {
  const raw = await invoke<string>(
    "update_permission_settings",
    {
      definition,
      readRecords:
        settings.read_records,
      writeRecords:
        settings.write_records,
      writeHistory:
        settings.write_history,
      runApprovedCommands:
        settings.run_approved_commands,
      networkAccess:
        settings.network_access,
      modifySystemFiles:
        settings.modify_system_files,
    },
  );

  const payload = JSON.parse(raw) as {
    status?: string;
    permissions?: PermissionSettings;
  };

  if (
    payload.status !== "success"
    || !payload.permissions
  ) {
    throw new Error(
      "Permission settings could not be updated.",
    );
  }

  return payload.permissions;
}
