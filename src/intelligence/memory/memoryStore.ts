import fs from "fs";
import path from "path";

const memoryPath = path.join("data", "memory", "memory.jsonl");

export function saveMemory(record: Record<string, unknown>): void {
  fs.mkdirSync(path.dirname(memoryPath), { recursive: true });

  const line = JSON.stringify({
    timestamp: new Date().toISOString(),
    ...record,
  });

  fs.appendFileSync(memoryPath, line + "\n", "utf-8");
}

export function readRecentMemory(limit = 10): string {
  if (!fs.existsSync(memoryPath)) return "";

  const raw = fs.readFileSync(memoryPath, "utf-8").trim();

  if (!raw) return "";

  const lines = raw.split("\n");
  return lines.slice(-limit).join("\n");
}
