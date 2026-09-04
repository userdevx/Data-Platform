import {
  processManualModelRequest,
} from "../bridge/modelBridge";

import {
  processNaturalIntelligenceRequest,
} from "../bridge/intelligenceBridge";

import type {
  NaturalIntelligenceResponse,
} from "../bridge/intelligenceBridge";

import type {
  ModelOption,
} from "../bridge/modelBridge";

import {
  isAutomaticModel,
} from "./modelSelection";


export type ModelRequestInput = {
  request: string;
  requestId: string;
  model: ModelOption;
  definitionPath: string;
};


async function submitAutomaticRequest(
  request: string,
  requestId: string,
  definitionPath: string,
): Promise<NaturalIntelligenceResponse> {
  return processNaturalIntelligenceRequest(
    request,
    definitionPath,
    requestId,
  );
}


async function submitManualRequest(
  input: ModelRequestInput,
): Promise<NaturalIntelligenceResponse> {
  return processManualModelRequest(
    input.request,
    input.model.option_id,
    "",
    {},
    input.requestId,
  );
}


export async function submitModelRequest(
  input: ModelRequestInput,
): Promise<NaturalIntelligenceResponse> {
  if (
    isAutomaticModel(
      input.model,
    )
  ) {
    return submitAutomaticRequest(
      input.request,
      input.requestId,
      input.definitionPath,
    );
  }

  return submitManualRequest(
    input,
  );
}
