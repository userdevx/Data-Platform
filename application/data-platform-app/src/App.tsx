import {
  useState,
} from "react";

import ButtonInterfacePage from "./pages/ButtonInterfacePage";
import DeveloperModeLayout from "./components/mode/DeveloperModeLayout";

import AppOverflowMenu, {
  type ConfigurationSection,
} from "./components/AppOverflowMenu";

import ConfigurationPanel from "./components/ConfigurationPanel";

import type {
  AppMode,
  DeveloperModePage,
} from "./types/appModes";

import "./App.css";


function App() {
  const [
    activeMode,
    setActiveMode,
  ] = useState<AppMode>("user");

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
  >(null);

  return (
    <main className="app-shell">
      <header className="app-utility-bar">
        <div className="app-utility-title">
          Data Platform
        </div>

        <div className="app-utility-actions">
          <AppOverflowMenu
            activeMode={activeMode}
            onModeChange={setActiveMode}
            onOpenConfiguration={
              setConfigurationSection
            }
          />
        </div>
      </header>

      <section className="app-content">
        {activeMode === "user" ? (
          <ButtonInterfacePage />
        ) : (
          <DeveloperModeLayout
            activePage={developerPage}
            onPageChange={
              setDeveloperPage
            }
          />
        )}
      </section>

      <ConfigurationPanel
        section={configurationSection}
        onClose={() => {
          setConfigurationSection(null);
        }}
      />
    </main>
  );
}

export default App;
