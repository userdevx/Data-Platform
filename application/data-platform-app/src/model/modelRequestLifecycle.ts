export type RequestLogLevel =
  | "info"
  | "success"
  | "error";


export type RequestLogEvent = {
  message: string;
  level: RequestLogLevel;
};


export function createRequestSubmittedEvent(
  modelDisplayName: string,
): RequestLogEvent {
  return {
    message:
      `Request submitted to ${modelDisplayName}`,
    level: "info",
  };
}


export function createRequestSucceededEvent(
  modelDisplayName: string,
): RequestLogEvent {
  return {
    message:
      `Response received from ${modelDisplayName}`,
    level: "success",
  };
}


export function isRequestCancellation(
  message: string,
): boolean {
  return message
    .toLowerCase()
    .includes("cancel");
}


export function createRequestFailureEvent(
  message: string,
): RequestLogEvent {
  if (
    isRequestCancellation(
      message,
    )
  ) {
    return {
      message:
        "Request cancelled",
      level: "info",
    };
  }

  return {
    message:
      "Runtime request failed",
    level: "error",
  };
}


export function normalizeRequestError(
  error: unknown,
): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return (
    "The request could not be completed."
  );
}
