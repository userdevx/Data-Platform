type DatabaseCreatedPageProps = {
  databaseName: string;
  databasePath: string;
  selectedFilePath: string;
  dataDriveFilePath: string;
  onOpenWorkspace: () => void;
  onConnectAnotherSource: () => void;
  onClose: () => void;
};

function getFileName(path: string) {
  return path.split("/").pop() || path;
}

function DatabaseCreatedPage({
  databaseName,
  databasePath,
  selectedFilePath,
  dataDriveFilePath,
  onOpenWorkspace,
  onConnectAnotherSource,
  onClose
}: DatabaseCreatedPageProps) {
  const selectedFileName = getFileName(dataDriveFilePath || selectedFilePath);

  return (
    <main className="welcome-page">
      <section className="welcome-card database-created-card">
        <div className="created-check" aria-hidden="true">
          ✓
        </div>

        <header className="created-header">
          <h1>Database Created</h1>
          <p>Your Data Engine database was created successfully.</p>
        </header>

        <section className="created-summary">
          <div className="summary-row">
            <span>Database name:</span>
            <strong>{databaseName}</strong>
          </div>

          <div className="summary-row">
            <span>Selected file:</span>
            <strong>{selectedFileName}</strong>
          </div>

          <div className="summary-row">
            <span>Storage type:</span>
            <strong>Data Engine Database</strong>
          </div>

          <div className="summary-row">
            <span>Database location:</span>
            <strong>{databasePath}</strong>
          </div>

          <div className="summary-row">
            <span>Status:</span>
            <strong className="success-text">Success</strong>
          </div>
        </section>

        <section className="bottom-actions created-actions">
          <button
            type="button"
            className="primary-button"
            onClick={onOpenWorkspace}
          >
            Open Workspace
          </button>

          <button
            type="button"
            className="secondary-button"
            onClick={onConnectAnotherSource}
          >
            Connect Another Source
          </button>

          <button type="button" className="quiet-button" onClick={onClose}>
            Close
          </button>
        </section>
      </section>
    </main>
  );
}

export default DatabaseCreatedPage;
