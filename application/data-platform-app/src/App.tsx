import {
  useState,
} from "react";

import ButtonInterfacePage
  from "./pages/ButtonInterfacePage";

import ApplicationsPage
  from "./pages/ApplicationsPage";

import DeveloperModeLayout
  from "./components/mode/DeveloperModeLayout";

import SourcePage
  from "./components/SourcePage";

import CreateDatabasePage
  from "./components/database/CreateDatabasePage";

import DatabaseCreatedPage
  from "./components/database/DatabaseCreatedPage";

import WorkspacePage
  from "./components/workspace/WorkspacePage";

import type {
  ConfigurationSection,
} from "./components/AppOverflowMenu";

import ConfigurationPanel
  from "./components/ConfigurationPanel";

import AppSidebar
  from "./components/shell/AppSidebar";


import type {
  AppMode,
  DeveloperModePage,
} from "./types/appModes";

import type {
  UserPage,
} from "./types/navigation";


import "./App.css";
import "./styles/shell.css";


type DataStage =
  | "source"
  | "create-database"
  | "database-created"
  | "workspace";


function App() {
  const [
    activeMode,
    setActiveMode,
  ] = useState<AppMode>(
    "user",
  );


  const [
    activeUserPage,
    setActiveUserPage,
  ] = useState<UserPage>(
    "intelligence",
  );


  const [
    developerPage,
    setDeveloperPage,
  ] = useState<DeveloperModePage>(
    "Terminal",
  );


  const [
    configurationSection,
    setConfigurationSection,
  ] = useState<
    ConfigurationSection | null
  >(
    null,
  );


  const [
    dataStage,
    setDataStage,
  ] = useState<DataStage>(
    "source",
  );


  const [
    selectedFilePath,
    setSelectedFilePath,
  ] = useState("");


  const [
    dataDriveFilePath,
    setDataDriveFilePath,
  ] = useState("");


  const [
    databaseName,
    setDatabaseName,
  ] = useState("");


  const [
    databasePath,
    setDatabasePath,
  ] = useState("");


  function changeMode(
    mode: AppMode,
  ): void {
    setConfigurationSection(
      null,
    );

    setActiveMode(
      mode,
    );
  }


  function changeUserPage(
    page: UserPage,
  ): void {
    setConfigurationSection(
      null,
    );

    setActiveMode(
      "user",
    );

    setActiveUserPage(
      page,
    );
  }


  function openSettings(): void {
    setActiveMode(
      "user",
    );

    setConfigurationSection(
      "memory",
    );
  }


  function closeDataFlow(): void {
    setActiveUserPage(
      "intelligence",
    );
  }


  function resetDataFlow(): void {
    setSelectedFilePath(
      "",
    );

    setDataDriveFilePath(
      "",
    );

    setDatabaseName(
      "",
    );

    setDatabasePath(
      "",
    );

    setDataStage(
      "source",
    );
  }


  function renderDataPage() {
    if (
      dataStage
      === "create-database"
    ) {
      return (
        <CreateDatabasePage
          selectedFilePath={
            selectedFilePath
          }
          dataDriveFilePath={
            dataDriveFilePath
          }
          onBack={() => {
            setDataStage(
              "source",
            );
          }}
          onClose={
            closeDataFlow
          }
          onCreated={(
            createdDatabaseName,
            createdDatabasePath,
          ) => {
            setDatabaseName(
              createdDatabaseName,
            );

            setDatabasePath(
              createdDatabasePath,
            );

            setDataStage(
              "database-created",
            );
          }}
        />
      );
    }


    if (
      dataStage
      === "database-created"
    ) {
      return (
        <DatabaseCreatedPage
          databaseName={
            databaseName
          }
          databasePath={
            databasePath
          }
          selectedFilePath={
            selectedFilePath
          }
          dataDriveFilePath={
            dataDriveFilePath
          }
          onOpenWorkspace={() => {
            setDataStage(
              "workspace",
            );
          }}
          onConnectAnotherSource={() => {
            resetDataFlow();

            setActiveUserPage(
              "data",
            );
          }}
          onClose={
            closeDataFlow
          }
        />
      );
    }


    if (
      dataStage
      === "workspace"
    ) {
      return (
        <WorkspacePage
          databaseName={
            databaseName
          }
          databasePath={
            databasePath
          }
          onOpenAgent={() => {
            setActiveUserPage(
              "intelligence",
            );
          }}
          onClose={() => {
            setDataStage(
              "source",
            );
          }}
        />
      );
    }


    return (
      <SourcePage
        onBack={
          closeDataFlow
        }
        onNext={(
          nextSelectedFilePath,
          nextDataDriveFilePath,
        ) => {
          setSelectedFilePath(
            nextSelectedFilePath,
          );

          setDataDriveFilePath(
            nextDataDriveFilePath,
          );

          setDataStage(
            "create-database",
          );
        }}
      />
    );
  }


  function renderUserPage() {
    if (
      activeUserPage
      === "applications"
    ) {
      return (
        <ApplicationsPage />
      );
    }


    if (
      activeUserPage
      === "data"
    ) {
      return (
        renderDataPage()
      );
    }


    return (
      <ButtonInterfacePage
          onOpenApplications={() => {
            changeUserPage(
              "applications",
            );
          }}
          onOpenData={() => {
            changeUserPage(
              "data",
            );
          }}
        />
    );
  }


  return (
    <div className="dw-app">
      <AppSidebar
        activeMode={
          activeMode
        }
        activePage={
          activeUserPage
        }
        settingsOpen={
          configurationSection
          !== null
        }
        onModeChange={
          changeMode
        }
        onPageChange={
          changeUserPage
        }
        onOpenSettings={
          openSettings
        }
      />


      <main className="dw-app__content">
        {
          activeMode === "user"
            ? (
              renderUserPage()
            )
            : (
              <DeveloperModeLayout
                activePage={
                  developerPage
                }
                onPageChange={
                  setDeveloperPage
                }
              />
            )
        }
      </main>


      <ConfigurationPanel
        section={
          configurationSection
        }
        onSectionChange={
          setConfigurationSection
        }
        onClose={() => {
          setConfigurationSection(
            null,
          );
        }}
      />
    </div>
  );
}


export default App;
