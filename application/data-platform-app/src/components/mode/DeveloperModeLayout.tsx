import type { DeveloperModePage } from "../../types/appModes";
import { developerModeNavigation } from "../../types/appModes";
import "./DeveloperModeLayout.css";

type DeveloperModeLayoutProps = {
  activePage: DeveloperModePage;
  onPageChange: (page: DeveloperModePage) => void;
};

export default function DeveloperModeLayout({
  activePage,
  onPageChange
}: DeveloperModeLayoutProps) {
  const activeItem = developerModeNavigation.find((item) => item.id === activePage);

  return (
    <section className="developer-mode-layout">
      <aside className="developer-mode-sidebar">
        <div className="developer-mode-brand">
          <div className="developer-mode-logo">⌘</div>

          <div>
            <strong>Developer Mode</strong>
            <span>Technical workspace</span>
          </div>
        </div>

        <nav className="developer-mode-nav" aria-label="Developer Mode navigation">
          {developerModeNavigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={activePage === item.id ? "active" : ""}
              onClick={() => onPageChange(item.id)}
              title={item.description}
            >
              <span>{item.label}</span>
              <small>{item.status}</small>
            </button>
          ))}
        </nav>
      </aside>

      <section className="developer-mode-content">
        <header className="developer-mode-header">
          <p>Developer Mode</p>
          <h2>{activeItem?.label ?? activePage}</h2>
          <span>{activeItem?.description}</span>
        </header>

        <div className="developer-mode-placeholder">
          <div className="developer-terminal-preview-header">
            <strong>{activePage}</strong>
            <span>Not connected yet</span>
          </div>

          <div className="developer-terminal-preview-body">
            <p>
              This area is reserved for Developer Mode tools. The terminal,
              Git tools, build tools, tests, logs, processes, and environment
              panels will be added after the mode system is tested.
            </p>

            <pre>{`Developer Mode Preview
Selected Tool: ${activePage}
Status: Planned
Main Application: Protected
Next Step: Connect one tool at a time`}</pre>
          </div>
        </div>
      </section>
    </section>
  );
}
