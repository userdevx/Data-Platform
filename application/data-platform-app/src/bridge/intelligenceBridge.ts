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

export async function getDataPlatformRoot(): Promise<string> {
  return invoke<string>("get_data_platform_root");
}
