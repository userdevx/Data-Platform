import {
  useEffect,
  useMemo,
  useState,
} from "react";
import { openUrl } from "@tauri-apps/plugin-opener";

import IntelligenceHeader from "../components/IntelligenceHeader";
import IntelligenceComposer from "../components/intelligence/IntelligenceComposer";
import IntelligenceResponsePanel from "../components/IntelligenceResponsePanel";
import AskHero from "../components/intelligence/AskHero";
import SystemStatusLine from "../components/intelligence/SystemStatusLine";
import StartIdeas from "../components/intelligence/StartIdeas";


import {
  cancelIntelligenceRequest,
  getIntelligenceDefinition,
  processNaturalIntelligenceRequest,
  type NaturalIntelligenceResponse,
} from "../bridge/intelligenceBridge";
import {
  cancelManualModelRequest,
  getModelOptions,
  processManualModelRequest,
  type ModelOption,
} from "../bridge/modelBridge";
import {
  executeModelRequest,
} from "../model/executeModelRequest";
import {
  requireSelectedModel,
  validateRequestSubmission,
} from "../model/requestValidation";
import {
  createRequestSubmittedEvent,
} from "../model/modelRequestLifecycle";

import {
  useModelSelection,
} from "../model/useModelSelection";

import { intelligenceConfig } from "../config/intelligenceConfig";

import "../styles/intelligencePage.css";

type RuntimeStatus =
  | "ready"
  | "thinking"
  | "success"
  | "error";

type SystemLogItem = {
  id: string;
  message: string;
  time: string;
  status: "success" | "info" | "error";
};

function getTimeLabel(): string {
  return new Date().toLocaleTimeString(
    [],
    {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    },
  );
}

function createLog(
  message: string,
  status: SystemLogItem["status"] = "info",
): SystemLogItem {
  return {
    id: crypto.randomUUID(),
    message,
    time: getTimeLabel(),
    status,
  };
}

function getDisplayStatus(
  status: RuntimeStatus,
): string {
  if (status === "thinking") {
    return "Working";
  }

  if (status === "error") {
    return "Needs attention";
  }

  return "Ready";
}

function getErrorMessage(
  error: unknown,
): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "The request could not be completed.";
}

export type ButtonInterfacePageProps = {
  onOpenApplications: () => void;
  onOpenData: () => void;
};


export default function ButtonInterfacePage({
  onOpenApplications,
  onOpenData,
}: ButtonInterfacePageProps) {
  const [
    requestText,
    setRequestText,
  ] = useState("");

  const [
    runtimeStatus,
    setRuntimeStatus,
  ] = useState<RuntimeStatus>("ready");

  const [
    response,
    setResponse,
  ] = useState<NaturalIntelligenceResponse | null>(
    null,
  );

  const [
    errorMessage,
    setErrorMessage,
  ] = useState("");

  const [
    ,
    setDisplayName,
  ] = useState(
    intelligenceConfig.fallbackDisplayName,
  );

  const [
    logs,
    setLogs,
  ] = useState<SystemLogItem[]>([]);

  const [
    modelOptions,
    setModelOptions,
  ] = useState<ModelOption[]>([]);

  const {
    selectedModelId,
    setSelectedModelId,
    selectedModel,
  } = useModelSelection(
    modelOptions,
  );

  const [
    modelsLoading,
    setModelsLoading,
  ] = useState(true);

  const [
    attachmentPaths,
    setAttachmentPaths,
  ] = useState<string[]>([]);

  const [
    activeRequestId,
    setActiveRequestId,
  ] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let isActive = true;

    setLogs([
      createLog(
        "System initialized",
        "success",
      ),
      createLog(
        "Data Engine connected",
        "success",
      ),
      createLog(
        "Intelligence runtime ready",
        "success",
      ),
    ]);

    void getIntelligenceDefinition(
      intelligenceConfig.definitionPath,
    )
      .then((definition) => {
        if (!isActive) {
          return;
        }

        const configuredName =
          definition.identity?.display_name
          || definition.identity?.name
          || intelligenceConfig
            .fallbackDisplayName;

        setDisplayName(configuredName);
      })
      .catch(() => {
        if (!isActive) {
          return;
        }

        setDisplayName(
          intelligenceConfig.fallbackDisplayName,
        );
      });

    void getModelOptions()
      .then((result) => {
        if (!isActive) {
          return;
        }

        if (result.status !== "success") {
          throw new Error(
            result.errors[0]
            ?? "Models could not be loaded.",
          );
        }

        const userModeAskModels =
          result.models.filter((model) => {
            if (model.option_id === "automatic") {
              return true;
            }

            if (!model.available) {
              return false;
            }

            const capabilities =
              model.capabilities ?? [];

            const blockedCapabilities = new Set([
              "semantic_similarity",
              "feature_extraction",
              "text_classification",
              "embedding",
              "embeddings",
            ]);

            const allowedCapabilities = new Set([
              "text_input",
              "text_generation",
              "chat",
              "conversation",
              "reasoning",
            ]);

            const hasBlockedCapability =
              capabilities.some((capability) =>
                blockedCapabilities.has(capability),
              );

            if (hasBlockedCapability) {
              return false;
            }

            return capabilities.some((capability) =>
              allowedCapabilities.has(capability),
            );
          });

        setModelOptions(userModeAskModels);

        const initialModel =
          userModeAskModels.find(
            (model) =>
              model.option_id === "automatic"
              && model.available,
          )
          ?? userModeAskModels.find(
            (model) => model.available,
          );

        setSelectedModelId(
          initialModel?.option_id ?? "automatic",
        );

        setLogs((current) => [
          createLog(
            `${result.models.filter(
              (model) => model.available,
            ).length} model options loaded`,
            "success",
          ),
          ...current,
        ]);
      })
      .catch((error: unknown) => {
        if (!isActive) {
          return;
        }

        const message =
          getErrorMessage(error);

        setErrorMessage(message);

        setLogs((current) => [
          createLog(
            "Model discovery failed",
            "error",
          ),
          ...current,
        ]);
      })
      .finally(() => {
        if (isActive) {
          setModelsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  async function openExternalUrl(
    url: string,
  ): Promise<void> {
    if (!url.trim()) {
      return;
    }

    try {
      await openUrl(url);

      setLogs((current) => [
        createLog(
          "Opened source link",
          "success",
        ),
        ...current,
      ].slice(0, 100));
    } catch (error) {
      const message =
        getErrorMessage(error);

      setErrorMessage(message);

      setLogs((current) => [
        createLog(
          "Could not open source link",
          "error",
        ),
        ...current,
      ].slice(0, 100));
    }
  }

  async function handleCancel(): Promise<void> {
    const requestId =
      activeRequestId;

    if (!requestId) {
      return;
    }

    try {
      if (
        selectedModelId
        === "automatic"
      ) {
        await cancelIntelligenceRequest(
          requestId,
        );
      } else {
        await cancelManualModelRequest(
          requestId,
        );
      }

      setLogs((current) => [
        createLog(
          "Cancellation requested",
          "info",
        ),
        ...current,
      ].slice(0, 100));

    } catch (error) {
      const message =
        getErrorMessage(error);

      setErrorMessage(
        message,
      );

      setLogs((current) => [
        createLog(
          "Cancellation failed",
          "error",
        ),
        ...current,
      ].slice(0, 100));
    }
  }


  async function handleAsk(): Promise<void> {
    if (runtimeStatus === "thinking") {
      return;
    }

    const cleanRequest =
      requestText.trim();

    const validationError =
      validateRequestSubmission({
        requestText,
        attachmentPaths,
        model: selectedModel,
      });

    if (validationError) {
      setRuntimeStatus("error");

      setErrorMessage(
        validationError.message,
      );

      setLogs((current) => [
        createLog(
          validationError.logMessage,
          "error",
        ),
        ...current,
      ].slice(0, 100));

      return;
    }

    const activeModel =
      requireSelectedModel(
        selectedModel,
      );

    const requestId =
      crypto.randomUUID();

    setActiveRequestId(
      requestId,
    );

    setRuntimeStatus("thinking");
    setErrorMessage("");
    setResponse(null);

    const submittedEvent =
      createRequestSubmittedEvent(
        activeModel.display_name,
      );

    setLogs((current) => [
      createLog(
        submittedEvent.message,
        submittedEvent.level,
      ),
      ...current,
    ].slice(0, 100));

    const execution =
      await executeModelRequest({
        request: cleanRequest,
        requestId,
        model: activeModel,
        definitionPath:
          intelligenceConfig.definitionPath,
      });

    if (
      execution.status
      === "success"
    ) {
      setResponse(
        execution.response,
      );
      setErrorMessage("");
    } else {
      setResponse(null);
      setErrorMessage(
        execution.errorMessage,
      );
    }

    setLogs((current) => [
      createLog(
        execution.event.message,
        execution.event.level,
      ),
      ...current,
    ].slice(0, 100));

    setActiveRequestId(
      null,
    );

    setRuntimeStatus("ready");
  }

  return (
    <main className="intelligence-page">
      <IntelligenceHeader
        title={
          intelligenceConfig.pageTitle
        }
        runtimeStatus={
          runtimeStatus
        }
        statusLabel={
          getDisplayStatus(
            runtimeStatus,
          )
        }
      />

      <AskHero>
        <IntelligenceComposer
          modelOptions={modelOptions}
          modelsLoading={modelsLoading}
          selectedModelId={selectedModelId}
          requestText={requestText}
          attachmentPaths={attachmentPaths}
          busy={runtimeStatus === "thinking"}
          errorMessage={errorMessage}
          onModelChange={setSelectedModelId}
          onRequestChange={setRequestText}
          onAttachmentChange={setAttachmentPaths}
          onSend={() => {
            void handleAsk();
          }}
          onCancel={() => {
            void handleCancel();
          }}
        />

      </AskHero>

        <StartIdeas
          onAsk={() => {
            document
              .querySelector<HTMLTextAreaElement>(
                ".dw-composer__input",
              )
              ?.focus();
          }}
          onConnect={onOpenData}
          onBuild={onOpenApplications}
        />

      {response || runtimeStatus === "thinking" ? (
        <IntelligenceResponsePanel
          response={response}
          onOpenUrl={openExternalUrl}
        />
      ) : null}

      <SystemStatusLine
        ready={runtimeStatus === "ready" || runtimeStatus === "success"}
        items={
          logs.length > 0
            ? logs.slice(0, 2).map((log) => log.message)
            : [getDisplayStatus(runtimeStatus)]
        }
      />
    </main>
  );
}
