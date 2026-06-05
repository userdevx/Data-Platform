export function reviewFailure(error: unknown): string {
  if (error instanceof Error) {
    return `Failure detected: ${error.message}`;
  }

  return "Failure detected: unknown error.";
}

export function updateCriteriaAfterFix(): string {
  return "Criteria updated after successful fix and retest.";
}
