import type { AgentDecision, AgentRequest } from "../types";
import { CONFIG } from "../config";
import { securityReview } from "../security/securityReview";
import { createPlan } from "../workflows/agentPlanner";
import { runTool, type ToolName } from "../tools/toolRegistry";
import { saveMemory } from "../memory/memoryStore";
import { reviewFailure } from "../workflows/failureReview";

export async function runAgent(request: AgentRequest): Promise<AgentDecision> {
  try {
    const security = securityReview(request.userInput);

    if (!security.passed) {
      const decision: AgentDecision = {
        requestSummary: request.userInput,
        selectedRoute: "blocked",
        modelSelected: CONFIG.openaiModel,
        toolRequested: null,
        reason: security.reason,
        riskLevel: security.riskLevel,
        permissionResult: security.permissionResult,
        securityResult: "failed",
        output: "Request blocked by security review.",
        nextAction: "Revise request or request manual review.",
      };

      saveMemory({ type: "security_block", decision });
      return decision;
    }

    const plan = await createPlan(request);

    if (security.permissionResult === "requires_approval") {
      const decision: AgentDecision = {
        requestSummary: plan.requestSummary,
        selectedRoute: plan.selectedRoute,
        modelSelected: CONFIG.openaiModel,
        toolRequested: plan.toolRequested,
        reason: "Action requires user approval before execution.",
        riskLevel: security.riskLevel,
        permissionResult: security.permissionResult,
        securityResult: "passed",
        output: "Approval required. Tool was not executed.",
        nextAction: "Ask user for confirmation.",
      };

      saveMemory({ type: "approval_required", decision });
      return decision;
    }

    const filePathMatch = request.userInput.match(/data\/[\w\-./]+/);
    const shouldReadFile =
      filePathMatch &&
      request.userInput.toLowerCase().includes("read");

    const toolName: ToolName = shouldReadFile
      ? "read_file"
      : "internet_search";

    const toolResult = await runTool(toolName, {
      folder: ".",
      content: plan.output,
      query: request.userInput,
      path: filePathMatch ? filePathMatch[0] : "",
    });

    const decision: AgentDecision = {
      requestSummary: plan.requestSummary,
      selectedRoute: shouldReadFile ? "file_read" : "internet_research",
      modelSelected: CONFIG.openaiModel,
      toolRequested: toolName,
      reason: shouldReadFile
        ? "Request asks to read a local data file."
        : "Request routed to Paige research workflow.",
      riskLevel: security.riskLevel,
      permissionResult: security.permissionResult,
      securityResult: "passed",
      output: toolResult.output,
      nextAction: toolResult.ok
        ? "Review answer and source details."
        : "Review error and retry.",
    };

    saveMemory({ type: "workflow_run", request, decision });
    return decision;
  } catch (error) {
    const failure = reviewFailure(error);

    const decision: AgentDecision = {
      requestSummary: request.userInput,
      selectedRoute: "failure_review",
      modelSelected: CONFIG.openaiModel,
      toolRequested: null,
      reason: failure,
      riskLevel: "medium",
      permissionResult: "blocked",
      securityResult: "failed",
      output: "Agent failed safely.",
      nextAction: "Review failure, fix issue, retest, then update criteria.",
    };

    saveMemory({ type: "failure", decision });
    return decision;
  }
}
