import fs from "fs";
import path from "path";
import { askModelWithSearch } from "../model/openaiAdapter";

function appendJsonl(filePath: string, record: unknown): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${JSON.stringify(record)}\n`, "utf-8");
}

export async function runPaigeResearch(question: string): Promise<string> {
  const query = question.trim();

  if (!query) {
    return "Ask a question first.";
  }

  const startedAt = new Date().toISOString();

  appendJsonl("data/paige/tasks.jsonl", {
    query,
    status: "running",
    created_at: startedAt,
  });

  try {
    const prompt = `
You are Paige, the Data Platform intelligence agent.

Answer the user's question clearly.
Use web search when current or outside information is useful.
Do not say "No results were found" unless the search tool truly fails.
If search results are limited, still answer from available knowledge and say that source coverage was limited.
Include useful source names or links when available.

User question:
${query}
`;

    const answer = await askModelWithSearch(prompt);

    appendJsonl("data/paige/answers.jsonl", {
      query,
      answer,
      status: "complete",
      created_at: new Date().toISOString(),
    });

    appendJsonl("data/records.jsonl", {
      source: "internet",
      category: "research",
      sensor_type: "paige_web_search_answer",
      value: query,
      unit: "answer",
      timestamp: new Date().toISOString(),
      metadata: {
        provider: "openai_web_search",
        answer,
      },
    });

    return answer;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);

    appendJsonl("data/paige/errors.jsonl", {
      query,
      error: message,
      status: "failed",
      created_at: new Date().toISOString(),
    });

    return `Paige search failed safely. ${message}`;
  }
}
