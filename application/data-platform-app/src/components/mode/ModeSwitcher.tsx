import type { AppMode } from "../../types/appModes";
import { modeOptions } from "../../types/appModes";
import "./ModeSwitcher.css";

type ModeSwitcherProps = {
  activeMode: AppMode;
  onModeChange: (mode: AppMode) => void;
};

export default function ModeSwitcher({
  activeMode,
  onModeChange
}: ModeSwitcherProps) {
  return (
    <section className="mode-switcher" aria-label="Application mode switcher">
      <div className="mode-switcher-copy">
        <p>Data Platform</p>
        <h1>{activeMode === "user" ? "User Mode" : "Developer Mode"}</h1>
      </div>

      <div className="mode-switcher-buttons">
        {modeOptions.map((option) => (
          <button
            key={option.id}
            type="button"
            className={activeMode === option.id ? "active" : ""}
            onClick={() => onModeChange(option.id)}
            title={option.description}
          >
            {option.label}
          </button>
        ))}
      </div>
    </section>
  );
}
