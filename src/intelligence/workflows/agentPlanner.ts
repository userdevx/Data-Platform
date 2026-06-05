import { z } from "zod";
import { askModel } from "../model/openaiAdapter";
import { buildContext } from "../context/contextBuilder";
import type { AgentRequest } from "../types";

const PlanSchema = z.object({
  requestSummary: z.string(),
  selectedRoute: z.string(),
  toolRequested: z
    .enum([
      "answer_only",
      "list_files",
      "create_note",
      "generate_report",
      "read_file"
    ])
    .nullable(),
  reason: z.string(),
  output: z.string(),
  nextAction: z.string(),
});

export type AgentPlan = z.infer<typeof PlanSchema>;

export async function createPlan(request: AgentRequest): Promise<AgentPlan> {
  const lower = request.userInput.toLowerCase();

  if (
    lower.includes("show the content") ||
    lower.includes("read file") ||
    lower.includes(".md") ||
    lower.includes(".txt")
  ) {
    return {
      requestSummary: request.userInput,
      selectedRoute: "read_file_route",
      toolRequested: "read_file",
      reason: "Detected file read request.",
      output: "Reading requested file.",
      nextAction: "Display file content.",
    };
  }

  if (
    lower.includes("create note") ||
    lower.includes("chat note")
  ) {
    return {
      requestSummary: request.userInput,
      selectedRoute: "create_note_route",
      toolRequested: "create_note",
      reason: "Detected note creation request.",
      output: "Creating note.",
      nextAction: "Save note to logs.",
    };
  }

  const context = buildContext(request);

  const prompt = `
You are the Data Platform Intelligence Agent.

Return ONLY valid JSON with this structure:
{
  "requestSummary": "",
  "selectedRoute": "",
  "toolRequested": "answer_only | list_files | create_note | generate_report | read_file | null",
  "reason": "",
  "output": "",
  "nextAction": ""
}

Context:
${context}
`;

  const raw = await askModel(prompt);

  try {
    const parsed = JSON.parse(raw);
    return PlanSchema.parse(parsed);
  } catch {
    return {
      requestSummary: request.userInput,
      selectedRoute: "answer_only",
      toolRequested: "answer_only",
      reason: "Model did not return valid JSON. Falling back to safe answer.",
      output: raw,
      nextAction: "Review model output format.",
    };
  }
}
