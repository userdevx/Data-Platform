import type { UserModePage } from "../../types/appModes";
import { userModeNavigation } from "../../types/appModes";
import "./UserModeLayout.css";

type UserModeLayoutProps = {
  activePage: UserModePage;
  onPageChange: (page: UserModePage) => void;
};

export default function UserModeLayout({
  activePage,
  onPageChange
}: UserModeLayoutProps) {
  const activeItem = userModeNavigation.find((item) => item.id === activePage);

  return (
    <section className="user-mode-layout">
      <aside className="user-mode-sidebar">
        <div className="user-mode-brand">
          <div className="user-mode-logo">▣</div>

          <div>
            <strong>User Mode</strong>
            <span>Application workspace</span>
          </div>
        </div>

        <nav className="user-mode-nav" aria-label="User Mode navigation">
          {userModeNavigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={activePage === item.id ? "active" : ""}
              onClick={() => onPageChange(item.id)}
              title={item.description}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="user-mode-content">
        <header className="user-mode-header">
          <p>User Mode</p>
          <h2>{activeItem?.label ?? activePage}</h2>
          <span>{activeItem?.description}</span>
        </header>

        <div className="user-mode-placeholder">
          <h3>{activePage}</h3>
          <p>
            This layout is prepared for the User Mode page structure. The
            current working Data Platform interface should be connected only
            after this framework is tested.
          </p>
        </div>
      </section>
    </section>
  );
}
