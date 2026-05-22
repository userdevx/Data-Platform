import { invoke } from "@tauri-apps/api/core";
import { useMemo, useState } from "react";

type CreateDatabaseResult = {
  success: boolean;
  message: string;
  database_name: string;
  database_path: string;
  source_file: string;
};

type CreateDatabasePageProps = {
  selectedFilePath: string;
  dataDriveFilePath: string;
  onBack: () => void;
  onClose: () => void;
  onCreated: (databaseName: string, databasePath: string) => void;
};

function getFileName(path: string) {
  return path.split("/").pop() || path;
}

function cleanDatabaseName(fileName: string) {
  return fileName
    .replace(/\.[^/.]+$/, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function CreateDatabasePage({
  selectedFilePath,
  dataDriveFilePath,
  onBack,
  onClose,
  onCreated
}: CreateDatabasePageProps) {
  const fileForDatabase = dataDriveFilePath || selectedFilePath;
  const selectedFileName = getFileName(fileForDatabase);

  const defaultDatabaseName = useMemo(
    () => cleanDatabaseName(selectedFileName || "new_database"),
    [selectedFileName]
  );

  const [databaseName, setDatabaseName] = useState(defaultDatabaseName);
  const [statusMessage, setStatusMessage] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  async function createDatabase() {
    if (!fileForDatabase) {
      setStatusMessage("No selected file found. Go back and connect a file first.");
      return;
    }

    if (!databaseName.trim()) {
      setStatusMessage("Enter a database name.");
      return;
    }

    try {
      setIsCreating(true);
      setStatusMessage("Creating database...");

      const result = await invoke<CreateDatabaseResult>("create_database", {
        databaseName: databaseName.trim(),
        selectedFilePath: fileForDatabase,
        storageType: "Data Engine Database"
      });

      if (!result.success) {
        setStatusMessage("Database creation failed.");
        return;
      }

      setStatusMessage(result.message);

      onCreated(result.database_name, result.database_path);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="welcome-page">
      <section className="welcome-card database-card">
        <button type="button" className="back-button" onClick={onBack}>
          ← Back
        </button>

        <header className="source-header database-header">
          <h1>Create Database</h1>
          <p>Create a Data Engine database from the selected file.</p>
        </header>

        <section className="database-form">
          <section className="database-field">
            <label>Selected file:</label>

            <div className="selected-file-card">
              <span className="file-badge">📄</span>

              <span className="selected-file-copy">
                <strong>{selectedFileName || "No file selected"}</strong>
                <small>{fileForDatabase}</small>
              </span>
            </div>
          </section>

          <section className="database-field">
            <label htmlFor="database-name">Database name:</label>

            <input
              id="database-name"
              className="database-input"
              value={databaseName}
              onChange={(event) => setDatabaseName(event.target.value)}
            />
          </section>

          <section className="database-field">
            <label>Storage type:</label>

            <div className="storage-type-box">
              <span className="storage-type-icon">🗄️</span>
              <strong>Data Engine Database</strong>
            </div>
          </section>

          <section className="database-info-box">
            <span>ℹ️</span>
            <p>
              This file is stored in the Data Drive. The database will be created
              using Data Engine and saved in your Data Drive.
            </p>
          </section>

          {statusMessage ? (
            <p className="status-message">{statusMessage}</p>
          ) : null}
        </section>

        <section className="bottom-actions">
          <button
            type="button"
            className="primary-button"
            onClick={createDatabase}
            disabled={isCreating}
          >
            {isCreating ? "Creating..." : "Create Database"}
          </button>

          <button type="button" className="secondary-button" onClick={onBack}>
            Back
          </button>

          <button type="button" className="quiet-button" onClick={onClose}>
            Close
          </button>
        </section>
      </section>
    </main>
  );
}

export default CreateDatabasePage;
