import { readRecentMemory } from "../memory/memoryStore";
import type { AgentRequest } from "../types";

export function buildContext(request: AgentRequest): string {
  const recentMemory = readRecentMemory(5);

  return `
# Agent Context

## Contact Name
${request.contactName}

## Description
${request.description}

## User Request
${request.userInput}

## Recent Relevant Memory
${recentMemory || "No recent memory."}

## Operating Rules
- Use minimal context.
- Do not expose secrets.
- Do not run unapproved commands.
- Check security before tools.
- Ask approval for high-risk actions.
- Log important workflow events.
`;
}
