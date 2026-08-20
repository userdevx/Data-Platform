import {
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  AppMode,
} from "../types/appModes";


export type ConfigurationSection =
  | "memory"
  | "personalization"
  | "permissions"
  | "system-details";


type AppOverflowMenuProps = {
  activeMode: AppMode;
  onModeChange: (
    mode: AppMode,
  ) => void;
  onOpenConfiguration: (
    section: ConfigurationSection,
  ) => void;
};


export default function AppOverflowMenu({
  activeMode,
  onModeChange,
  onOpenConfiguration,
}: AppOverflowMenuProps) {
  const [open, setOpen] = useState(false);

  const menuRef =
    useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(
      event: PointerEvent,
    ): void {
      const target =
        event.target as Node | null;

      if (
        target
        && menuRef.current
        && !menuRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }

    function handleKeyDown(
      event: KeyboardEvent,
    ): void {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener(
      "pointerdown",
      handlePointerDown,
    );

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      window.removeEventListener(
        "pointerdown",
        handlePointerDown,
      );

      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [open]);

  function selectMode(
    mode: AppMode,
  ): void {
    onModeChange(mode);
    setOpen(false);
  }

  function selectConfiguration(
    section: ConfigurationSection,
  ): void {
    onOpenConfiguration(section);
    setOpen(false);
  }

  return (
    <div
      ref={menuRef}
      className="app-overflow"
    >
      <button
        type="button"
        className="app-overflow-button"
        aria-label="Open application menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setOpen((current) => !current);
        }}
      >
        <span aria-hidden="true">
          •••
        </span>
      </button>

      {open ? (
        <div
          className="app-overflow-menu"
          role="menu"
        >
          <button
            type="button"
            role="menuitemradio"
            aria-checked={activeMode === "user"}
            className="app-overflow-item"
            onClick={() => {
              selectMode("user");
            }}
          >
            <span>User Mode</span>

            {activeMode === "user" ? (
              <span
                className="app-overflow-check"
                aria-hidden="true"
              >
                ✓
              </span>
            ) : null}
          </button>

          <button
            type="button"
            role="menuitemradio"
            aria-checked={activeMode === "developer"}
            className="app-overflow-item"
            onClick={() => {
              selectMode("developer");
            }}
          >
            <span>
              Developer Mode
            </span>

            {activeMode === "developer" ? (
              <span
                className="app-overflow-check"
                aria-hidden="true"
              >
                ✓
              </span>
            ) : null}
          </button>

          <div
            className="app-overflow-divider"
            role="separator"
          />

          <button
            type="button"
            role="menuitem"
            className="app-overflow-item"
            onClick={() => {
              selectConfiguration("memory");
            }}
          >
            Memory
          </button>

          <button
            type="button"
            role="menuitem"
            className="app-overflow-item"
            onClick={() => {
              selectConfiguration(
                "personalization",
              );
            }}
          >
            Personalization
          </button>

          <button
            type="button"
            role="menuitem"
            className="app-overflow-item"
            onClick={() => {
              selectConfiguration(
                "permissions",
              );
            }}
          >
            Permissions
          </button>

          <button
            type="button"
            role="menuitem"
            className="app-overflow-item"
            onClick={() => {
              selectConfiguration(
                "system-details",
              );
            }}
          >
            System Details
          </button>
        </div>
      ) : null}
    </div>
  );
}
