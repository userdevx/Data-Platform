import fs from "fs";
import path from "path";

export type PaigeSourceRecord = {
  query: string;
  title: string;
  url: string;
  snippet: string;
  provider: string;
  scrapedText?: string;
  createdAt: string;
};

function appendJsonl(filePath: string, record: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${JSON.stringify(record)}\n`, "utf-8");
}

export function storePaigeSources(query: string, sources: PaigeSourceRecord[]): void {
  for (const source of sources) {
    appendJsonl("data/paige/sources.jsonl", source);

    appendJsonl("data/records.jsonl", {
      source: "internet",
      category: "research",
      sensor_type: "web_search_result",
      value: query,
      unit: "search_result",
      timestamp: source.createdAt,
      metadata: {
        provider: source.provider,
        title: source.title,
        url: source.url,
        snippet: source.snippet,
        scraped_text: source.scrapedText ?? "",
      },
    });
  }
}

export function storePaigeAnswer(query: string, answer: string, sourceCount: number): void {
  appendJsonl("data/paige/answers.jsonl", {
    query,
    answer,
    source_count: sourceCount,
    created_at: new Date().toISOString(),
  });
}
