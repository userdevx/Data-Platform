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
  model: ModelOption;
  definitionPath: string;
};


async function submitAutomaticRequest(
  request: string,
  definitionPath: string,
): Promise<NaturalIntelligenceResponse> {
  return processNaturalIntelligenceRequest(
    request,
    definitionPath,
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
      input.definitionPath,
    );
  }

  return submitManualRequest(
    input,
  );
}
