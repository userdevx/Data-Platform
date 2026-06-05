import type { PermissionResult, RiskLevel } from "../types";

const blockedPatterns = [
  "ignore previous instructions",
  "reveal your system prompt",
  "show api key",
  "print env",
  "disable security",
  "bypass permission",
];

export function detectPromptInjection(input: string): boolean {
  const lower = input.toLowerCase();
  return blockedPatterns.some((pattern) => lower.includes(pattern));
}

export function classifyRisk(input: string): RiskLevel {
  const lower = input.toLowerCase();

  if (
    lower.includes("delete") ||
    lower.includes("send email") ||
    lower.includes("schedule meeting") ||
    lower.includes("post to") ||
    lower.includes("run command") ||
    lower.includes("install")
  ) {
    return "high";
  }

  if (
    lower.includes("create file") ||
    lower.includes("edit file") ||
    lower.includes("api") ||
    lower.includes("tool")
  ) {
    return "medium";
  }

  return "low";
}

export function permissionCheck(risk: RiskLevel): PermissionResult {
  if (risk === "high") return "requires_approval";
  return "approved";
}

export function securityReview(input: string): {
  passed: boolean;
  riskLevel: RiskLevel;
  permissionResult: PermissionResult;
  reason: string;
} {
  if (detectPromptInjection(input)) {
    return {
      passed: false,
      riskLevel: "high",
      permissionResult: "blocked",
      reason: "Prompt injection or security bypass attempt detected.",
    };
  }

  const riskLevel = classifyRisk(input);
  const permissionResult = permissionCheck(riskLevel);

  return {
    passed: true,
    riskLevel,
    permissionResult,
    reason: "Security review completed.",
  };
}
