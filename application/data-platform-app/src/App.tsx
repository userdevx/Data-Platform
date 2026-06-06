import { useState } from "react";
import ButtonInterfacePage from "./pages/ButtonInterfacePage";
import DeveloperModeLayout from "./components/mode/DeveloperModeLayout";
import ModeSwitcher from "./components/mode/ModeSwitcher";
import type { AppMode, DeveloperModePage } from "./types/appModes";
import "./App.css";

function App() {
  const [activeMode, setActiveMode] = useState<AppMode>("user");
  const [developerPage, setDeveloperPage] = useState<DeveloperModePage>("Terminal");

  return (
    <main className="app-shell">
      <header className="app-utility-bar">
        <div className="app-utility-title">Data Platform</div>

        <div className="app-utility-actions">
          <ModeSwitcher activeMode={activeMode} onModeChange={setActiveMode} />
        </div>
      </header>

      <section className="app-content">
        {activeMode === "user" ? (
          <ButtonInterfacePage />
        ) : (
          <DeveloperModeLayout
            activePage={developerPage}
            onPageChange={setDeveloperPage}
          />
        )}
      </section>
    </main>
  );
}

export default App;
