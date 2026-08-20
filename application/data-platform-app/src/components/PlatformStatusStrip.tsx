import {
  useEffect,
  useState,
} from "react";

import {
  getEngineStatus,
} from "../bridge/engineBridge";

import type {
  EngineStatus,
} from "../types/appTypes";


type StatusItem = {
  label: string;
  value: string;
  status: string;
};


function formatStatusValue(
  value: string,
): string {
  const normalized =
    value.trim().toLowerCase();

  if (!normalized) {
    return value;
  }

  return (
    normalized.charAt(0).toUpperCase()
    + normalized.slice(1)
  );
}


function buildStatusItems(
  engineStatus: EngineStatus,
): StatusItem[] {
  return [
    {
      label: "Sources",
      value: String(
        engineStatus.connected_sources,
      ),
      status:
        engineStatus.connected_sources > 0
          ? "Connected"
          : "None",
    },
    {
      label: "Raw Records",
      value: String(
        engineStatus.record_count,
      ),
      status:
        engineStatus.record_count > 0
          ? "Ready"
          : "Empty",
    },
    {
      label: "Definitions",
      value:
        formatStatusValue(
          engineStatus.definition_status,
        ),
      status: "Current",
    },
    {
      label: "Validation",
      value:
        formatStatusValue(
          engineStatus.validation_status,
        ),
      status: "Configured",
    },
    {
      label: "Runtime",
      value:
        formatStatusValue(
          engineStatus.status,
        ),
      status: "Current",
    },
  ];
}


export default function PlatformStatusStrip() {
  const [
    engineStatus,
    setEngineStatus,
  ] = useState<EngineStatus | null>(null);

  const [
    errorMessage,
    setErrorMessage,
  ] = useState("");

  async function loadStatus(): Promise<void> {
    try {
      const status =
        await getEngineStatus();

      setEngineStatus(status);
      setErrorMessage("");
    } catch (error) {
      setEngineStatus(null);

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "System details could not be loaded.",
      );
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  if (errorMessage) {
    return (
      <p
        className="configuration-error"
        role="alert"
      >
        {errorMessage}
      </p>
    );
  }

  if (!engineStatus) {
    return (
      <p className="configuration-status">
        Loading system details…
      </p>
    );
  }

  const statusItems =
    buildStatusItems(engineStatus);

  return (
    <div className="system-detail-list">
      {statusItems.map((item) => (
        <div
          key={item.label}
          className="system-detail-row"
        >
          <span
            className="system-detail-dot"
            aria-hidden="true"
          />

          <span className="system-detail-name">
            {item.label}
          </span>

          <strong className="system-detail-value">
            {item.value}
          </strong>

          <small className="system-detail-status">
            {item.status}
          </small>
        </div>
      ))}
    </div>
  );
}
