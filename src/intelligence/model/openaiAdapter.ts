import OpenAI from "openai";
import { CONFIG } from "../config";

const client = new OpenAI({
  apiKey: CONFIG.openaiApiKey,
});

export async function askModel(input: string): Promise<string> {
  const response = await client.responses.create({
    model: CONFIG.openaiModel,
    input,
  });

  return response.output_text || "Paige could not generate an answer.";
}

export async function askModelWithSearch(input: string): Promise<string> {
  const response = await client.responses.create({
    model: CONFIG.openaiModel,
    tools: [
      {
        type: "web_search_preview",
      },
    ],
    input,
  });

  return response.output_text || "Paige could not generate an answer.";
}
