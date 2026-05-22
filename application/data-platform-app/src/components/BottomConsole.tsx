import type { AppMode } from "../types/appTypes";

function BottomConsole({ activeMode }: { activeMode: AppMode }) {
  if (activeMode === "user") {
    return (
      <footer className="bottom-console">
        <span className="console-label">CON</span>
        <span className="console-text">
          [Info] Report generation complete. Ready for download.
        </span>
      </footer>
    );
  }

  return (
    <footer className="bottom-console">
      <span className="console-label">CON</span>
      <span className="console-text">
        &gt;_ engine query --sensor cpu_usage --limit 50
      </span>
    </footer>
  );
}

export default BottomConsole;
