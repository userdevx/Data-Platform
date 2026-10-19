import type { ReactNode } from "react";
import { BRAND } from "../../config/brand";
import type { UserPage } from "../../types/navigation";
import "./AppSidebar.css";

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

const ChatIcon = () => <Icon><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /></Icon>;
const AppsIcon = () => (
  <Icon>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <path d="M17.5 14v7M14 17.5h7" />
  </Icon>
);
const SettingsIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
  </Icon>
);
const TerminalIcon = () => <Icon><path d="M4 17l6-5-6-5M12 19h8" /></Icon>;

export type AppSidebarProps = {
  activePage: UserPage;
  onNavigate: (page: UserPage) => void;
  showApplications: boolean;
  onOpenSettings: () => void;
  onOpenDeveloperMode: () => void;
};

export default function AppSidebar({
  activePage,
  onNavigate,
  showApplications,
  onOpenSettings,
  onOpenDeveloperMode,
}: AppSidebarProps) {
  const items: { id: UserPage; label: string; icon: ReactNode }[] = [
    { id: "intelligence", label: "Intelligence", icon: <ChatIcon /> },
    ...(showApplications
      ? [{ id: "applications" as const, label: "Applications", icon: <AppsIcon /> }]
      : []),
  ];

  return (
    <nav className="dw-sidebar" aria-label={`${BRAND.product} navigation`}>
      <div className="dw-sidebar__brand">
        <svg width="30" height="30" viewBox="0 0 28 28" aria-hidden="true">
          <rect width="28" height="28" rx="8" fill="#3b82f6" />
          <path d="M9 8.5h5a5.5 5.5 0 0 1 0 11H9z" fill="none" stroke="#ffffff" strokeWidth="2.2" />
        </svg>
        <span>{BRAND.product}</span>
      </div>

      <ul className="dw-sidebar__list">
        {items.map((item) => {
          const active =
            item.id === activePage ||
            (item.id === "applications" && activePage === "workspace");
          return (
            <li key={item.id}>
              <button
                type="button"
                className={active ? "dw-sidebar__item is-active" : "dw-sidebar__item"}
                aria-current={active ? "page" : undefined}
                onClick={() => onNavigate(item.id)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="dw-sidebar__footer">
        <button type="button" className="dw-sidebar__item" onClick={onOpenSettings}>
          <SettingsIcon />
          <span>Settings</span>
        </button>
        <button type="button" className="dw-sidebar__item" onClick={onOpenDeveloperMode}>
          <TerminalIcon />
          <span>Developer Mode</span>
        </button>
      </div>
    </nav>
  );
}
