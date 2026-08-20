import {
  useEffect,
  useState,
} from "react";

import type {
  ConfigurationSection,
} from "./AppOverflowMenu";

import PlatformStatusStrip from "./PlatformStatusStrip";

import {
  getIntelligenceDefinition,
  updateMemorySettings,
  updatePermissionSettings,
  updatePersonalizationSettings,
  type MemorySettings,
  type PermissionSettings,
  type PersonalizationSettings,
} from "../bridge/intelligenceBridge";

import {
  intelligenceConfig,
} from "../config/intelligenceConfig";


type ConfigurationPanelProps = {
  section:
    | ConfigurationSection
    | null;
  onClose: () => void;
};


type MemoryDefinition = {
  memory?: Partial<MemorySettings>;
};


type PersonalizationDefinition = {
  identity?: {
    display_name?: string;
    role?: string;
    description?: string;
  };
};


type PermissionDefinition = {
  permissions?: Partial<PermissionSettings>;
};


function getTitle(
  section: ConfigurationSection,
): string {
  switch (section) {
    case "memory":
      return "Memory";

    case "personalization":
      return "Personalization";

    case "permissions":
      return "Permissions";

    case "system-details":
      return "System Details";
  }
}


function getDefaultMemorySettings(): MemorySettings {
  return {
    enabled: false,
    read: false,
    write: false,
    automatic_recall: false,
  };
}


export default function ConfigurationPanel({
  section,
  onClose,
}: ConfigurationPanelProps) {
  const [
    memorySettings,
    setMemorySettings,
  ] = useState<MemorySettings>(
    getDefaultMemorySettings,
  );

  const [
    memoryLoading,
    setMemoryLoading,
  ] = useState(false);

  const [
    memorySaving,
    setMemorySaving,
  ] = useState(false);

  const [
    memoryError,
    setMemoryError,
  ] = useState("");

  const [
    memoryStatus,
    setMemoryStatus,
  ] = useState("");

  const [
    personalizationSettings,
    setPersonalizationSettings,
  ] = useState<PersonalizationSettings>({
    display_name: "",
    role: "",
    description: "",
  });

  const [
    personalizationLoading,
    setPersonalizationLoading,
  ] = useState(false);

  const [
    personalizationSaving,
    setPersonalizationSaving,
  ] = useState(false);

  const [
    personalizationError,
    setPersonalizationError,
  ] = useState("");

  const [
    personalizationStatus,
    setPersonalizationStatus,
  ] = useState("");

  const [
    permissionSettings,
    setPermissionSettings,
  ] = useState<PermissionSettings>({
    read_records: false,
    write_records: false,
    write_history: false,
    run_approved_commands: false,
    network_access: false,
    modify_system_files: false,
  });

  const [
    permissionLoading,
    setPermissionLoading,
  ] = useState(false);

  const [
    permissionSaving,
    setPermissionSaving,
  ] = useState(false);

  const [
    permissionError,
    setPermissionError,
  ] = useState("");

  const [
    permissionStatus,
    setPermissionStatus,
  ] = useState("");


  useEffect(() => {
    if (section !== "memory") {
      return;
    }

    let active = true;

    setMemoryLoading(true);
    setMemoryError("");
    setMemoryStatus("");

    getIntelligenceDefinition(
      intelligenceConfig.definitionPath,
    )
      .then((definition) => {
        if (!active) {
          return;
        }

        const memoryDefinition =
          definition as MemoryDefinition;

        const memory =
          memoryDefinition.memory ?? {};

        setMemorySettings({
          enabled:
            memory.enabled ?? false,
          read:
            memory.read
            ?? memory.enabled
            ?? false,
          write:
            memory.write
            ?? memory.enabled
            ?? false,
          automatic_recall:
            memory.automatic_recall
            ?? memory.enabled
            ?? false,
        });
      })
      .catch((error) => {
        if (!active) {
          return;
        }

        setMemoryError(
          error instanceof Error
            ? error.message
            : "Memory settings could not be loaded.",
        );
      })
      .finally(() => {
        if (active) {
          setMemoryLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [section]);


  useEffect(() => {
    if (section !== "personalization") {
      return;
    }

    let active = true;

    setPersonalizationLoading(true);
    setPersonalizationError("");
    setPersonalizationStatus("");

    getIntelligenceDefinition(
      intelligenceConfig.definitionPath,
    )
      .then((definition) => {
        if (!active) {
          return;
        }

        const personalizationDefinition =
          definition as PersonalizationDefinition;

        const identity =
          personalizationDefinition.identity ?? {};

        setPersonalizationSettings({
          display_name:
            identity.display_name ?? "",
          role:
            identity.role ?? "",
          description:
            identity.description ?? "",
        });
      })
      .catch((error) => {
        if (!active) {
          return;
        }

        setPersonalizationError(
          error instanceof Error
            ? error.message
            : "Personalization settings could not be loaded.",
        );
      })
      .finally(() => {
        if (active) {
          setPersonalizationLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [section]);


  useEffect(() => {
    if (section !== "permissions") {
      return;
    }

    let active = true;

    setPermissionLoading(true);
    setPermissionError("");
    setPermissionStatus("");

    getIntelligenceDefinition(
      intelligenceConfig.definitionPath,
    )
      .then((definition) => {
        if (!active) {
          return;
        }

        const permissionDefinition =
          definition as PermissionDefinition;

        const permissions =
          permissionDefinition.permissions ?? {};

        setPermissionSettings({
          read_records:
            permissions.read_records ?? false,
          write_records:
            permissions.write_records ?? false,
          write_history:
            permissions.write_history ?? false,
          run_approved_commands:
            permissions.run_approved_commands
            ?? false,
          network_access:
            permissions.network_access ?? false,
          modify_system_files:
            permissions.modify_system_files
            ?? false,
        });
      })
      .catch((error) => {
        if (!active) {
          return;
        }

        setPermissionError(
          error instanceof Error
            ? error.message
            : "Permission settings could not be loaded.",
        );
      })
      .finally(() => {
        if (active) {
          setPermissionLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [section]);


  async function handleMemoryEnabledChange(
    enabled: boolean,
  ): Promise<void> {
    if (
      memorySaving
      || memoryLoading
    ) {
      return;
    }

    const nextSettings: MemorySettings = {
      enabled,
      read: enabled,
      write: enabled,
      automatic_recall: enabled,
    };

    setMemorySaving(true);
    setMemoryError("");
    setMemoryStatus("");

    try {
      const saved =
        await updateMemorySettings(
          nextSettings,
          intelligenceConfig.definitionPath,
        );

      setMemorySettings(saved);

      setMemoryStatus(
        saved.enabled
          ? "Memory enabled."
          : "Memory disabled.",
      );
    } catch (error) {
      setMemoryError(
        error instanceof Error
          ? error.message
          : "Memory settings could not be updated.",
      );
    } finally {
      setMemorySaving(false);
    }
  }


  async function handlePersonalizationSave(): Promise<void> {
    if (
      personalizationLoading
      || personalizationSaving
    ) {
      return;
    }

    const displayName =
      personalizationSettings.display_name.trim();

    const role =
      personalizationSettings.role.trim();

    const description =
      personalizationSettings.description.trim();

    if (!displayName) {
      setPersonalizationError(
        "Enter a display name.",
      );
      return;
    }

    if (!role) {
      setPersonalizationError(
        "Enter a role.",
      );
      return;
    }

    if (!description) {
      setPersonalizationError(
        "Enter a description.",
      );
      return;
    }

    setPersonalizationSaving(true);
    setPersonalizationError("");
    setPersonalizationStatus("");

    try {
      const saved =
        await updatePersonalizationSettings(
          {
            display_name: displayName,
            role,
            description,
          },
          intelligenceConfig.definitionPath,
        );

      setPersonalizationSettings(saved);

      setPersonalizationStatus(
        "Personalization saved.",
      );
    } catch (error) {
      setPersonalizationError(
        error instanceof Error
          ? error.message
          : "Personalization settings could not be updated.",
      );
    } finally {
      setPersonalizationSaving(false);
    }
  }


  async function handlePermissionChange(
    key: keyof PermissionSettings,
  ): Promise<void> {
    if (
      permissionLoading
      || permissionSaving
    ) {
      return;
    }

    const nextSettings: PermissionSettings = {
      ...permissionSettings,
      [key]: !permissionSettings[key],
    };

    setPermissionSaving(true);
    setPermissionError("");
    setPermissionStatus("");

    try {
      const saved =
        await updatePermissionSettings(
          nextSettings,
          intelligenceConfig.definitionPath,
        );

      setPermissionSettings(saved);

      setPermissionStatus(
        "Permissions updated.",
      );
    } catch (error) {
      setPermissionError(
        error instanceof Error
          ? error.message
          : "Permission settings could not be updated.",
      );
    } finally {
      setPermissionSaving(false);
    }
  }


  if (!section) {
    return null;
  }

  return (
    <div
      className="configuration-overlay"
      role="presentation"
      onMouseDown={(event) => {
        if (
          event.target
          === event.currentTarget
        ) {
          onClose();
        }
      }}
    >
      <section
        className="configuration-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="configuration-panel-title"
      >
        <header className="configuration-panel-header">
          <div>
            <p className="configuration-panel-eyebrow">
              Settings
            </p>

            <h2 id="configuration-panel-title">
              {getTitle(section)}
            </h2>
          </div>

          <button
            type="button"
            className="configuration-close-button"
            aria-label="Close settings"
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <div className="configuration-panel-body">
          {section === "memory" ? (
            <div className="memory-settings">
              <div className="memory-setting-row">
                <div className="memory-setting-copy">
                  <h3>
                    Enable memory
                  </h3>

                  <p>
                    Allow the active Intelligence Runtime
                    to recall and store relevant memory
                    through the Data Engine.
                  </p>
                </div>

                <button
                  type="button"
                  className={[
                    "memory-toggle",
                    memorySettings.enabled
                      ? "memory-toggle-enabled"
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  role="switch"
                  aria-checked={
                    memorySettings.enabled
                  }
                  aria-label="Enable memory"
                  disabled={
                    memoryLoading
                    || memorySaving
                  }
                  onClick={() => {
                    void handleMemoryEnabledChange(
                      !memorySettings.enabled,
                    );
                  }}
                >
                  <span className="memory-toggle-track">
                    <span className="memory-toggle-thumb" />
                  </span>
                </button>
              </div>

              <div className="memory-settings-summary">
                <div>
                  <span>Read memory</span>
                  <strong>
                    {memorySettings.read
                      ? "On"
                      : "Off"}
                  </strong>
                </div>

                <div>
                  <span>Write memory</span>
                  <strong>
                    {memorySettings.write
                      ? "On"
                      : "Off"}
                  </strong>
                </div>

                <div>
                  <span>
                    Automatic recall
                  </span>
                  <strong>
                    {memorySettings.automatic_recall
                      ? "On"
                      : "Off"}
                  </strong>
                </div>
              </div>

              {memoryLoading ? (
                <p className="configuration-status">
                  Loading memory settings…
                </p>
              ) : null}

              {memorySaving ? (
                <p className="configuration-status">
                  Saving memory settings…
                </p>
              ) : null}

              {memoryStatus ? (
                <p className="configuration-success">
                  {memoryStatus}
                </p>
              ) : null}

              {memoryError ? (
                <p
                  className="configuration-error"
                  role="alert"
                >
                  {memoryError}
                </p>
              ) : null}
            </div>
          ) : null}

          {section === "personalization" ? (
            <div className="personalization-settings">
              <div className="configuration-field">
                <label htmlFor="personalization-display-name">
                  Display name
                </label>

                <input
                  id="personalization-display-name"
                  type="text"
                  value={
                    personalizationSettings.display_name
                  }
                  disabled={
                    personalizationLoading
                    || personalizationSaving
                  }
                  onChange={(event) => {
                    setPersonalizationSettings(
                      (current) => ({
                        ...current,
                        display_name:
                          event.target.value,
                      }),
                    );
                  }}
                />
              </div>

              <div className="configuration-field">
                <label htmlFor="personalization-role">
                  Role
                </label>

                <input
                  id="personalization-role"
                  type="text"
                  value={
                    personalizationSettings.role
                  }
                  disabled={
                    personalizationLoading
                    || personalizationSaving
                  }
                  onChange={(event) => {
                    setPersonalizationSettings(
                      (current) => ({
                        ...current,
                        role:
                          event.target.value,
                      }),
                    );
                  }}
                />
              </div>

              <div className="configuration-field">
                <label htmlFor="personalization-description">
                  Description
                </label>

                <textarea
                  id="personalization-description"
                  rows={5}
                  value={
                    personalizationSettings.description
                  }
                  disabled={
                    personalizationLoading
                    || personalizationSaving
                  }
                  onChange={(event) => {
                    setPersonalizationSettings(
                      (current) => ({
                        ...current,
                        description:
                          event.target.value,
                      }),
                    );
                  }}
                />
              </div>

              <div className="configuration-actions">
                <button
                  type="button"
                  className="configuration-save-button"
                  disabled={
                    personalizationLoading
                    || personalizationSaving
                  }
                  onClick={() => {
                    void handlePersonalizationSave();
                  }}
                >
                  {personalizationSaving
                    ? "Saving…"
                    : "Save"}
                </button>
              </div>

              {personalizationLoading ? (
                <p className="configuration-status">
                  Loading personalization…
                </p>
              ) : null}

              {personalizationStatus ? (
                <p className="configuration-success">
                  {personalizationStatus}
                </p>
              ) : null}

              {personalizationError ? (
                <p
                  className="configuration-error"
                  role="alert"
                >
                  {personalizationError}
                </p>
              ) : null}
            </div>
          ) : null}

          {section === "permissions" ? (
            <div className="permission-settings">
              {[
                {
                  key: "read_records" as const,
                  label: "Read records",
                  description:
                    "Allow the runtime to read records from the Data Engine.",
                },
                {
                  key: "write_records" as const,
                  label: "Write records",
                  description:
                    "Allow the runtime to write approved records.",
                },
                {
                  key: "write_history" as const,
                  label: "Write history",
                  description:
                    "Allow completed Intelligence requests to be recorded.",
                },
                {
                  key: "run_approved_commands" as const,
                  label: "Run approved commands",
                  description:
                    "Allow execution of commands that have been approved by policy.",
                },
                {
                  key: "network_access" as const,
                  label: "Network access",
                  description:
                    "Allow runtime capabilities that require network access.",
                },
                {
                  key: "modify_system_files" as const,
                  label: "Modify system files",
                  description:
                    "Allow runtime operations that can modify system files.",
                },
              ].map((permission) => (
                <div
                  key={permission.key}
                  className="permission-setting-row"
                >
                  <div className="permission-setting-copy">
                    <h3>
                      {permission.label}
                    </h3>

                    <p>
                      {permission.description}
                    </p>
                  </div>

                  <button
                    type="button"
                    className={[
                      "memory-toggle",
                      permissionSettings[
                        permission.key
                      ]
                        ? "memory-toggle-enabled"
                        : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    role="switch"
                    aria-checked={
                      permissionSettings[
                        permission.key
                      ]
                    }
                    aria-label={
                      permission.label
                    }
                    disabled={
                      permissionLoading
                      || permissionSaving
                    }
                    onClick={() => {
                      void handlePermissionChange(
                        permission.key,
                      );
                    }}
                  >
                    <span className="memory-toggle-track">
                      <span className="memory-toggle-thumb" />
                    </span>
                  </button>
                </div>
              ))}

              {permissionLoading ? (
                <p className="configuration-status">
                  Loading permissions…
                </p>
              ) : null}

              {permissionSaving ? (
                <p className="configuration-status">
                  Saving permissions…
                </p>
              ) : null}

              {permissionStatus ? (
                <p className="configuration-success">
                  {permissionStatus}
                </p>
              ) : null}

              {permissionError ? (
                <p
                  className="configuration-error"
                  role="alert"
                >
                  {permissionError}
                </p>
              ) : null}
            </div>
          ) : null}

          {section === "system-details" ? (
            <div className="system-details-settings">
              <p className="configuration-section-description">
                View current platform status.
              </p>

              <PlatformStatusStrip />
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
