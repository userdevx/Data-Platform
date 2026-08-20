import type {
  ModelOption,
} from "../bridge/modelBridge";


export type RequestValidationInput = {
  requestText: string;
  attachmentPaths: readonly string[];
  model: ModelOption | null;
};


export type RequestValidationError = {
  message: string;
  logMessage: string;
};


function hasRequestInput(
  requestText: string,
  attachmentPaths: readonly string[],
): boolean {
  return (
    Boolean(requestText.trim())
    || attachmentPaths.length > 0
  );
}


function isAvailableModel(
  model: ModelOption | null,
): model is ModelOption {
  return Boolean(
    model
    && model.available,
  );
}


function supportsAttachments(
  model: ModelOption,
): boolean {
  return (
    model.option_id === "automatic"
    || model.capabilities.includes(
      "image_input",
    )
  );
}


export function validateRequestSubmission(
  input: RequestValidationInput,
): RequestValidationError | null {
  const {
    requestText,
    attachmentPaths,
    model,
  } = input;

  if (
    !hasRequestInput(
      requestText,
      attachmentPaths,
    )
  ) {
    return {
      message:
        "Enter a request or attach a file.",
      logMessage:
        "Request rejected: no input",
    };
  }

  if (!isAvailableModel(model)) {
    return {
      message:
        "Select an available model.",
      logMessage:
        "Request rejected: no model selected",
    };
  }

  if (
    attachmentPaths.length > 0
    && !supportsAttachments(model)
  ) {
    return {
      message:
        "The selected model does not "
        + "support image input.",
      logMessage:
        "Selected model does not "
        + "support attachments",
    };
  }

  return null;
}


export function requireSelectedModel(
  model: ModelOption | null,
): ModelOption {
  if (!model) {
    throw new Error(
      "A validated request requires "
      + "an available model.",
    );
  }

  return model;
}
