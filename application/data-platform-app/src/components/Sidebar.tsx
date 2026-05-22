import type { AppMode, AppPage } from "../types/appTypes";

type SidebarProps = {
  activeMode: AppMode;
  activePage: AppPage;
  setActiveMode: (mode: AppMode) => void;
  setActivePage: (page: AppPage) => void;
};

type NavItem = {
  id: AppPage;
  label: string;
  title: string;
};

const developerPages: NavItem[] = [
  { id: "home", label: "HOME", title: "Home / Workspace" },
  { id: "ingestion", label: "ING", title: "Data Ingestion" },
  { id: "lakehouse", label: "LAKE", title: "Lakehouse Storage" },
  { id: "processing", label: "PROC", title: "Processing Pipelines" },
  { id: "query", label: "SQL", title: "Query and SQL Analysis" },
  { id: "analytics", label: "ANL", title: "Analytics and Dashboards" },
  { id: "monitoring", label: "MON", title: "Monitoring" },
  { id: "jobs", label: "JOB", title: "Jobs and Logs" },
  { id: "settings", label: "SET", title: "Settings" }
];

const userPages: NavItem[] = [
  { id: "home", label: "HOME", title: "Home / Workspace" },
  { id: "analytics", label: "ANL", title: "Analytics" },
  { id: "query", label: "SQL", title: "Query Viewer" },
  { id: "reports", label: "REP", title: "Reports" },
  { id: "monitoring", label: "MON", title: "Monitoring" },
  { id: "settings", label: "SET", title: "Settings" }
];

function Sidebar({
  activeMode,
  activePage,
  setActiveMode,
  setActivePage
}: SidebarProps) {
  const pages = activeMode === "developer" ? developerPages : userPages;

  function switchMode(mode: AppMode) {
    setActiveMode(mode);
    setActivePage("home");
  }

  return (
    <aside className="sidebar">
      <div className="brand-circle">DP</div>

      <div className="nav-label">WORKSPACE</div>

      <div className="mode-switch">
        <button
          className={activeMode === "developer" ? "mode-button active" : "mode-button"}
          onClick={() => switchMode("developer")}
          type="button"
        >
          Dev
        </button>

        <button
          className={activeMode === "user" ? "mode-button active" : "mode-button"}
          onClick={() => switchMode("user")}
          type="button"
        >
          User
        </button>
      </div>

      <nav className="nav-items" aria-label="Main navigation">
        {pages.map((page) => (
          <button
            key={page.id}
            title={page.title}
            aria-label={page.title}
            className={activePage === page.id ? "nav-item active" : "nav-item"}
            onClick={() => setActivePage(page.id)}
            type="button"
          >
            <span className="nav-item-label">{page.label}</span>
            <span className="nav-item-title">{page.title}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
