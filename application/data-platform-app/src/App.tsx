import { useState } from "react";
import CreateDatabasePage from "./components/database/CreateDatabasePage";
import DatabaseCreatedPage from "./components/database/DatabaseCreatedPage";
import SourcePage from "./components/SourcePage";
import WelcomePage from "./components/WelcomePage";
import WorkspacePage from "./components/workspace/WorkspacePage";

type AppPage =
  | "welcome"
  | "source"
  | "create-database"
  | "database-created"
  | "workspace";

type CreatedDatabase = {
  databaseName: string;
  databasePath: string;
  selectedFilePath: string;
  dataDriveFilePath: string;
};

function App() {
  const [page, setPage] = useState<AppPage>("welcome");
  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [dataDriveFilePath, setDataDriveFilePath] = useState("");
  const [createdDatabase, setCreatedDatabase] = useState<CreatedDatabase>({
    databaseName: "",
    databasePath: "",
    selectedFilePath: "",
    dataDriveFilePath: ""
  });

  if (page === "workspace") {
    return (
      <WorkspacePage
        databaseName={createdDatabase.databaseName}
        databasePath={createdDatabase.databasePath}
        onClose={() => setPage("welcome")}
      />
    );
  }

  if (page === "database-created") {
    return (
      <DatabaseCreatedPage
        databaseName={createdDatabase.databaseName}
        databasePath={createdDatabase.databasePath}
        selectedFilePath={createdDatabase.selectedFilePath}
        dataDriveFilePath={createdDatabase.dataDriveFilePath}
        onOpenWorkspace={() => setPage("workspace")}
        onConnectAnotherSource={() => setPage("source")}
        onClose={() => setPage("welcome")}
      />
    );
  }

  if (page === "create-database") {
    return (
      <CreateDatabasePage
        selectedFilePath={selectedFilePath}
        dataDriveFilePath={dataDriveFilePath}
        onBack={() => setPage("source")}
        onClose={() => setPage("welcome")}
        onCreated={(databaseName, databasePath) => {
          setCreatedDatabase({
            databaseName,
            databasePath,
            selectedFilePath,
            dataDriveFilePath
          });

          setPage("database-created");
        }}
      />
    );
  }

  if (page === "source") {
    return (
      <SourcePage
        onBack={() => setPage("welcome")}
        onNext={(selectedPath, storedPath) => {
          setSelectedFilePath(selectedPath);
          setDataDriveFilePath(storedPath);
          setPage("create-database");
        }}
      />
    );
  }

  return <WelcomePage onConnectData={() => setPage("source")} />;
}

export default App;
