import { open } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";

type UserLocation = {
  id: string;
  label: string;
  path: string;
};

type DirectoryEntry = {
  name: string;
  path: string;
  entry_type: string;
  size: number | null;
};

type ConnectionResult = {
  success: boolean;
  message: string;
  source_type: string;
  path: string | null;
  storage_path: string | null;
};

type SourcePageProps = {
  onBack: () => void;
  onNext: (selectedFilePath: string, dataDriveFilePath: string) => void;
};

function SourcePage({ onBack, onNext }: SourcePageProps) {
  const [locations, setLocations] = useState<UserLocation[]>([]);
  const [activeLocationPath, setActiveLocationPath] = useState("");
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [selectedPath, setSelectedPath] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [dataDriveFilePath, setDataDriveFilePath] = useState("");
  const [statusMessage, setStatusMessage] = useState(
    "Files selected. Choose a path or select a file."
  );

  async function loadLocations() {
    try {
      const systemLocations = await invoke<UserLocation[]>("get_user_locations");
      setLocations(systemLocations);

      const downloads =
        systemLocations.find((location) => location.id === "downloads") ||
        systemLocations[0];

      if (downloads) {
        setActiveLocationPath(downloads.path);
        await loadDirectory(downloads.path);
      }
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function loadDirectory(path: string) {
    try {
      setActiveLocationPath(path);

      const directoryEntries = await invoke<DirectoryEntry[]>("read_directory", {
        path
      });

      setEntries(directoryEntries);
    } catch (error) {
      setEntries([]);
      setStatusMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    void loadLocations();
  }, []);

  function resetConnectionState() {
    setIsConnected(false);
    setDataDriveFilePath("");
  }

  async function choosePath() {
    resetConnectionState();

    try {
      setStatusMessage("Opening file picker...");

      const selected = await open({
        multiple: false,
        directory: false,
        title: "Choose a data file"
      });

      if (typeof selected === "string") {
        setSelectedPath(selected);
        setStatusMessage("Path selected. Click Connect Data next.");
        return;
      }

      setStatusMessage("No file selected.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function connectData() {
    if (!selectedPath) {
      setStatusMessage("Select a file before connecting data.");
      return;
    }

    try {
      const result = await invoke<ConnectionResult>("connect_data", {
        sourceType: "files",
        path: selectedPath
      });

      setIsConnected(result.success);
      setDataDriveFilePath(result.storage_path || "");
      setStatusMessage(`${result.message} Click Next to create a database.`);
    } catch (error) {
      setIsConnected(false);
      setDataDriveFilePath("");
      setStatusMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function nextStep() {
    if (!isConnected) {
      setStatusMessage("Click Connect Data first. Then click Next.");
      return;
    }

    if (!selectedPath) {
      setStatusMessage("Select a file before creating a database.");
      return;
    }

    onNext(selectedPath, dataDriveFilePath);
  }

  async function openDataDriveFile() {
    if (!dataDriveFilePath) {
      setStatusMessage("No stored file is available yet.");
      return;
    }

    try {
      await openPath(dataDriveFilePath);
      setStatusMessage("Stored data opened.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function formatSize(size: number | null) {
    if (size === null) {
      return "—";
    }

    if (size < 1024) {
      return `${size} B`;
    }

    if (size < 1024 * 1024) {
      return `${Math.round(size / 1024)} KB`;
    }

    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  return (
    <main className="welcome-page">
      <section className="welcome-card source-card">
        <button type="button" className="back-button" onClick={onBack}>
          ← Back
        </button>

        <header className="source-header">
          <h1>Choose Files</h1>
          <p>Select files from your system and connect them to the Data Platform.</p>
        </header>

        <section className="source-list">
          <label className="source-row active">
            <input type="radio" name="source" checked readOnly />

            <span className="source-icon" aria-hidden="true">
              📁
            </span>

            <span className="source-copy">
              <strong>Files</strong>
              <small>File source • Path needed</small>
            </span>

            <button
              type="button"
              className="source-action"
              onClick={(event) => {
                event.preventDefault();
                void choosePath();
              }}
            >
              Choose Path
            </button>
          </label>
        </section>

        <section className="file-browser">
          <aside className="file-sidebar">
            {locations.map((location) => (
              <button
                key={location.id}
                type="button"
                className={
                  activeLocationPath === location.path
                    ? "location-row active"
                    : "location-row"
                }
                onClick={() => {
                  resetConnectionState();
                  void loadDirectory(location.path);
                }}
              >
                {location.label}
              </button>
            ))}

            <button
              type="button"
              className="location-row"
              onClick={() => void choosePath()}
            >
              Other Locations
            </button>
          </aside>

          <section className="file-list">
            <div className="file-list-header">
              <span>Name</span>
              <span>Type</span>
              <span>Size</span>
            </div>

            {entries.length === 0 ? (
              <p className="empty-files">No readable files found here.</p>
            ) : (
              entries.slice(0, 100).map((entry) => (
                <button
                  key={entry.path}
                  type="button"
                  className={
                    selectedPath === entry.path ? "file-row active" : "file-row"
                  }
                  onClick={() => {
                    resetConnectionState();

                    if (entry.entry_type === "Folder") {
                      void loadDirectory(entry.path);
                      return;
                    }

                    setSelectedPath(entry.path);
                    setStatusMessage("Path selected. Click Connect Data next.");
                  }}
                >
                  <span>{entry.name}</span>
                  <span>{entry.entry_type}</span>
                  <span>{formatSize(entry.size)}</span>
                </button>
              ))
            )}
          </section>
        </section>

        {selectedPath ? (
          <p className="selected-path-line">
            Selected path: <strong>{selectedPath}</strong>
          </p>
        ) : null}

        {statusMessage ? (
          <p className={isConnected ? "status-message connected" : "status-message"}>
            {statusMessage}
          </p>
        ) : null}

        {dataDriveFilePath ? (
          <section className="storage-panel">
            <p>
              Data Drive storage: <strong>{dataDriveFilePath}</strong>
            </p>

            <button
              type="button"
              className="storage-button"
              onClick={() => void openDataDriveFile()}
            >
              Open Data
            </button>
          </section>
        ) : null}

        <section className="bottom-actions">
          <button
            type="button"
            className="primary-button"
            onClick={connectData}
          >
            Connect Data
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={nextStep}
          >
            Next
          </button>

          <button
            type="button"
            className="quiet-button"
            onClick={onBack}
          >
            Close
          </button>
        </section>
      </section>
    </main>
  );
}

export default SourcePage;
