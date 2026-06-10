import "./UserModeSidebar.css";

export type UserModePage = "Workspace" | "Data" | "Paige";

type UserModeSidebarProps = {
  activePage: UserModePage;
  onPageChange: (page: UserModePage) => void;
};

const navItems: {
  id: UserModePage;
  label: string;
  description: string;
  icon: string;
}[] = [
  {
    id: "Workspace",
    label: "Workspace",
    description: "View platform activity.",
    icon: "▦"
  },
  {
    id: "Data",
    label: "Data",
    description: "Connect and organize data.",
    icon: "◫"
  },
  {
    id: "Paige",
    label: "Paige",
    description: "Ask questions and review answers.",
    icon: "✦"
  }
];

export default function UserModeSidebar({
  activePage,
  onPageChange
}: UserModeSidebarProps) {
  return (
    <aside className="user-sidebar" aria-label="Data Platform navigation">
      <div className="user-sidebar-brand">
        <div className="user-sidebar-logo" aria-hidden="true">
          ▣
        </div>

        <div className="user-sidebar-title-block">
          <strong>Data Platform</strong>
          <span>Interactive workspace</span>
        </div>
      </div>

      <nav className="user-sidebar-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            type="button"
            className={activePage === item.id ? "active" : ""}
            onClick={() => onPageChange(item.id)}
            title={item.description}
            aria-label={item.label}
          >
            <span className="user-sidebar-icon" aria-hidden="true">
              {item.icon}
            </span>
            <span className="user-sidebar-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
