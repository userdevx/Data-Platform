export interface SkillCriteria {
  skillName: string;
  version: string;
  requiredSuccessfulRuns: number;
  successfulRuns: number;
  failedRuns: number;
  trustLevel: "untrusted" | "testing" | "trusted";
}

export const workflowSkillCriteria: SkillCriteria = {
  skillName: "workflow_management",
  version: "1.0.0",
  requiredSuccessfulRuns: 3,
  successfulRuns: 0,
  failedRuns: 0,
  trustLevel: "testing",
};
