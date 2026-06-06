import { useEffect, useRef, useState } from "react";
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
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  function selectMode(mode: AppMode) {
    onModeChange(mode);
    setIsOpen(false);
  }

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!menuRef.current) return;

      if (!menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  return (
    <div className="mode-menu-wrap" ref={menuRef}>
      <button
        type="button"
        className={isOpen ? "mode-dot-button active" : "mode-dot-button"}
        aria-label="Open application menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        <span></span>
        <span></span>
        <span></span>
      </button>

      {isOpen ? (
        <div className="mode-menu" role="menu">
          {modeOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              role="menuitem"
              className={activeMode === option.id ? "active" : ""}
              onClick={() => selectMode(option.id)}
            >
              <span>{option.label}</span>
              {activeMode === option.id ? <small>Active</small> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
