export type RiskLevel = "low" | "medium" | "high";

export type PermissionResult = "approved" | "requires_approval" | "blocked";

export interface AgentRequest {
  contactName: string;
  description: string;
  userInput: string;
}

export interface AgentDecision {
  requestSummary: string;
  selectedRoute: string;
  modelSelected: string;
  toolRequested: string | null;
  reason: string;
  riskLevel: RiskLevel;
  permissionResult: PermissionResult;
  securityResult: "passed" | "failed";
  output: string;
  nextAction: string;
}

export interface ToolResult {
  ok: boolean;
  output: string;
}
