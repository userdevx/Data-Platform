import fs from "fs";
import path from "path";
import type { ToolResult } from "../types";
import { runPaigeResearch } from "../workflows/paigeResearchWorkflow";

export type ToolName =
  | "answer_only"
  | "list_files"
  | "create_note"
  | "generate_report"
  | "read_file"
  | "internet_search";

export async function runTool(
  toolName: ToolName,
  args: Record<string, string>
): Promise<ToolResult> {
  if (toolName === "answer_only") {
    const query = args.query ?? args.content ?? "";

    if (query.trim()) {
      const output = await runPaigeResearch(query);
      return { ok: true, output };
    }

    return { ok: true, output: "Ask a question first." };
  }

  if (toolName === "internet_search") {
    const query = args.query ?? args.content ?? "";

    if (!query.trim()) {
      return { ok: false, output: "Ask a question first." };
    }

    const output = await runPaigeResearch(query);
    return { ok: true, output };
  }

  if (toolName === "list_files") {
    const folder = args.folder ?? ".";
    const files = fs.readdirSync(folder).join("\n");
    return { ok: true, output: files || "No files found." };
  }

  if (toolName === "create_note") {
    const filePath = path.join("data", "logs", "chat_note.md");
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, args.content ?? "", "utf-8");
    return { ok: true, output: `Created note: ${filePath}` };
  }

  if (toolName === "generate_report") {
    const filePath = path.join("data", "reports", "workflow_report.md");
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, args.content ?? "", "utf-8");
    return { ok: true, output: `Created report: ${filePath}` };
  }

  if (toolName === "read_file") {
    const requestedPath = args.path ?? args.filePath ?? "";

    if (!requestedPath) {
      return { ok: false, output: "Missing file path." };
    }

    if (!requestedPath.startsWith("data/")) {
      return { ok: false, output: "Blocked: read_file only allows files inside data/." };
    }

    if (!fs.existsSync(requestedPath)) {
      return { ok: false, output: `File not found: ${requestedPath}` };
    }

    const content = fs.readFileSync(requestedPath, "utf-8");
    return { ok: true, output: content };
  }

  return { ok: false, output: `Unknown tool: ${toolName}` };
}
