import type {
  NaturalIntelligenceResponse,
} from "../bridge/intelligenceBridge";

import {
  submitModelRequest,
} from "./modelRequest";

import type {
  ModelRequestInput,
} from "./modelRequest";

import {
  createRequestFailureEvent,
  createRequestSucceededEvent,
  normalizeRequestError,
} from "./modelRequestLifecycle";

import type {
  RequestLogEvent,
} from "./modelRequestLifecycle";


export type ModelExecutionSuccess = {
  status: "success";
  response: NaturalIntelligenceResponse;
  event: RequestLogEvent;
};


export type ModelExecutionFailure = {
  status: "error";
  errorMessage: string;
  event: RequestLogEvent;
};


export type ModelExecutionResult =
  | ModelExecutionSuccess
  | ModelExecutionFailure;


function validateModelResponse(
  response: NaturalIntelligenceResponse,
): void {
  if (
    response.status !== "success"
  ) {
    throw new Error(
      response.answer
      || "The request failed.",
    );
  }
}


export async function executeModelRequest(
  input: ModelRequestInput,
): Promise<ModelExecutionResult> {
  try {
    const response =
      await submitModelRequest(
        input,
      );

    validateModelResponse(
      response,
    );

    return {
      status: "success",
      response,
      event:
        createRequestSucceededEvent(
          input.model.display_name,
        ),
    };

  } catch (error) {
    const errorMessage =
      normalizeRequestError(
        error,
      );

    return {
      status: "error",
      errorMessage,
      event:
        createRequestFailureEvent(
          errorMessage,
        ),
    };
  }
}
