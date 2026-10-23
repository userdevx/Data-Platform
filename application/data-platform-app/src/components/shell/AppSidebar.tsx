import type { ReactNode } from "react";

import { BRAND } from "../../config/brand";

import type {
  AppMode,
} from "../../types/appModes";

import type {
  UserPage,
} from "../../types/navigation";

import DataWorcLogo from "./DataWorcLogo";

import "./AppSidebar.css";


function Icon({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}


export type AppSidebarProps = {
  activeMode: AppMode;
  activePage: UserPage;
  settingsOpen: boolean;

  onModeChange: (
    mode: AppMode,
  ) => void;

  onPageChange: (
    page: UserPage,
  ) => void;

  onOpenSettings: () => void;
};


type NavigationItem = {
  id: UserPage;
  label: string;
  icon: ReactNode;
};


const navigationItems: NavigationItem[] = [
  {
    id: "intelligence",
    label: "Intelligence",
    icon: (
      <Icon>
        <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />
      </Icon>
    ),
  },

  {
    id: "applications",
    label: "Applications",
    icon: (
      <Icon>
        <rect x="4" y="4" width="6" height="6" rx="1" />
        <rect x="14" y="4" width="6" height="6" rx="1" />
        <rect x="4" y="14" width="6" height="6" rx="1" />
        <rect x="14" y="14" width="6" height="6" rx="1" />
      </Icon>
    ),
  },

  {
    id: "data",
    label: "Data",
    icon: (
      <Icon>
        <ellipse cx="12" cy="5" rx="7" ry="3" />
        <path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />
        <path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      </Icon>
    ),
  },
];


export default function AppSidebar({
  activeMode,
  activePage,
  settingsOpen,
  onModeChange,
  onPageChange,
  onOpenSettings,
}: AppSidebarProps) {
  const developerActive =
    activeMode === "developer";


  function selectPage(
    page: UserPage,
  ): void {
    onModeChange("user");
    onPageChange(page);
  }


  return (
    <nav
      className="dw-sidebar"
      aria-label={`${BRAND.product} navigation`}
    >
      <div className="dw-sidebar__brand">
        <DataWorcLogo
          className="dw-sidebar__logo"
        />
      </div>


      <ul className="dw-sidebar__list">
        {navigationItems.map((item) => {
          const active =
            activeMode === "user"
            && !settingsOpen
            && activePage === item.id;

          return (
            <li key={item.id}>
              <button
                type="button"
                className={
                  active
                    ? "dw-sidebar__item is-active"
                    : "dw-sidebar__item"
                }
                aria-current={
                  active
                    ? "page"
                    : undefined
                }
                onClick={() => {
                  selectPage(
                    item.id,
                  );
                }}
              >
                {item.icon}

                <span>
                  {item.label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>


      <div className="dw-sidebar__footer">
        <button
          type="button"
          className={
            activeMode === "user"
            && settingsOpen
              ? "dw-sidebar__item is-active"
              : "dw-sidebar__item"
          }
          onClick={() => {
            onModeChange("user");
            onOpenSettings();
          }}
        >
          <Icon>
            <circle
              cx="12"
              cy="12"
              r="3"
            />

            <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
          </Icon>

          <span>
            Settings
          </span>
        </button>


        <button
          type="button"
          className={
            developerActive
              ? "dw-sidebar__item is-active"
              : "dw-sidebar__item"
          }
          aria-current={
            developerActive
              ? "page"
              : undefined
          }
          onClick={() => {
            onModeChange(
              developerActive
                ? "user"
                : "developer",
            );
          }}
        >
          <Icon>
            <path d="M4 17l6-5-6-5M12 19h8" />
          </Icon>

          <span>
            Developer Mode
          </span>
        </button>
      </div>
    </nav>
  );
}
