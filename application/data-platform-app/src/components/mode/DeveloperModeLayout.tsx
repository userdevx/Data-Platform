import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";
import type { DeveloperModePage } from "../../types/appModes";
import { developerModeNavigation } from "../../types/appModes";
import "./DeveloperModeLayout.css";

type DeveloperModeLayoutProps = {
  activePage: DeveloperModePage;
  onPageChange: (page: DeveloperModePage) => void;
};

type DeveloperTerminalContext = {
  working_directory: string;
  operating_system: string;
  shell: string;
  project_root_found: boolean;
  message: string;
};

type DeveloperTerminalResponse = {
  success: boolean;
  command: string;
  working_directory: string;
  shell: string;
  exit_code: number | null;
  stdout: string;
  stderr: string;
  suggestion: string;
  message: string;
  timestamp: number;
};

const commandGroups: Record<DeveloperModePage, string[]> = {
  Terminal: [
    "pwd",
    "ls",
    "git status --short",
    "python3 --version",
    "node --version",
    "npm --version"
  ],
  Git: [
    "git status --short",
    "git log --oneline -5",
    "git branch --show-current"
  ],
  Build: [
    "cd application/data-platform-app && npm run build",
    "cd application/data-platform-app/src-tauri && cargo check"
  ],
  Tests: [
    "source venv/bin/activate && python -m pytest",
    "source venv/bin/activate && python -m pytest tests/test_ui_actions.py"
  ],
  Logs: [
    "tail -n 80 engine/agents/agent.log",
    "ls -la logs",
    "find data -maxdepth 3 -type f | head -40"
  ],
  Processes: [
    "ps aux | grep -E 'tauri|vite|python|node' | grep -v grep",
    "pgrep -af 'tauri|vite|python|node'"
  ],
  Environment: [
    "uname -a",
    "echo $SHELL",
    "pwd",
    "python3 --version",
    "node --version",
    "npm --version",
    "rustc --version",
    "cargo --version"
  ]
};

function formatTerminalOutput(result: DeveloperTerminalResponse) {
  return [
    `$ ${result.command}`,
    "",
    result.stdout ? result.stdout.trimEnd() : "",
    result.stderr ? result.stderr.trimEnd() : "",
    "",
    `Exit code: ${result.exit_code ?? "unknown"}`,
    `Status: ${result.success ? "success" : "error"}`,
    `Folder: ${result.working_directory}`,
    `Shell: ${result.shell}`,
    "",
    `Suggestion: ${result.suggestion}`
  ]
    .filter(Boolean)
    .join("\n");
}

export default function DeveloperModeLayout({
  activePage,
  onPageChange
}: DeveloperModeLayoutProps) {
  const activeItem = developerModeNavigation.find((item) => item.id === activePage);
  const quickCommands = commandGroups[activePage];

  const [terminalContext, setTerminalContext] =
    useState<DeveloperTerminalContext | null>(null);

  const [command, setCommand] = useState(quickCommands[0]);
  const [output, setOutput] = useState("Terminal ready. Enter a command or choose a quick command.");
  const [isRunning, setIsRunning] = useState(false);
  const [lastStatus, setLastStatus] = useState("Ready");

  async function loadTerminalContext() {
    try {
      const context = await invoke<DeveloperTerminalContext>(
        "get_developer_terminal_context"
      );

      setTerminalContext(context);
    } catch (error) {
      setOutput(error instanceof Error ? error.message : String(error));
      setLastStatus("Error");
    }
  }

  async function runCommand(commandToRun = command) {
    const cleanCommand = commandToRun.trim();

    if (!cleanCommand) {
      setOutput("Enter a command first.");
      setLastStatus("Waiting");
      return;
    }

    try {
      setIsRunning(true);
      setLastStatus("Running");
      setOutput(`$ ${cleanCommand}\n\nRunning...`);

      const result = await invoke<DeveloperTerminalResponse>(
        "run_developer_terminal_command",
        {
          request: {
            command: cleanCommand
          }
        }
      );

      setOutput(formatTerminalOutput(result));
      setLastStatus(result.success ? "Success" : "Error");
    } catch (error) {
      setOutput(error instanceof Error ? error.message : String(error));
      setLastStatus("Error");
    } finally {
      setIsRunning(false);
    }
  }

  async function copyOutput() {
    await navigator.clipboard.writeText(output);
    setLastStatus("Copied");
  }

  function clearOutput() {
    setOutput("Terminal cleared.");
    setLastStatus("Cleared");
  }

  function runCommandOnEnter(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      void runCommand();
    }
  }

  useEffect(() => {
    void loadTerminalContext();
  }, []);

  useEffect(() => {
    const nextCommand = commandGroups[activePage][0];
    setCommand(nextCommand);
    setOutput(`${activePage} ready. Enter a command or choose a quick command.`);
    setLastStatus("Ready");
  }, [activePage]);

  return (
    <section className="developer-mode-layout">
      <aside className="developer-mode-sidebar">
        <div className="developer-mode-brand">
          <div className="developer-mode-logo">⌘</div>

          <div>
            <strong>Developer Mode</strong>
            <span>System workspace</span>
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
              {item.label}
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

        <section className="developer-terminal-card">
          <div className="developer-terminal-top">
            <div>
              <h3>{activePage}</h3>
              <p>
                Commands run through the operating system from the detected Data Platform project folder.
              </p>
            </div>

            <strong
              className={
                lastStatus === "Success"
                  ? "status-good"
                  : lastStatus === "Error"
                    ? "status-bad"
                    : ""
              }
            >
              {lastStatus}
            </strong>
          </div>

          <div className="developer-context-grid">
            <div>
              <span>Folder</span>
              <strong>{terminalContext?.working_directory ?? "Detecting..."}</strong>
            </div>

            <div>
              <span>Shell</span>
              <strong>{terminalContext?.shell ?? "Detecting..."}</strong>
            </div>

            <div>
              <span>OS</span>
              <strong>{terminalContext?.operating_system ?? "Detecting..."}</strong>
            </div>
          </div>

          <div className="developer-command-row">
            <input
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              onKeyDown={runCommandOnEnter}
              placeholder="Enter command..."
            />

            <button
              type="button"
              onClick={() => void runCommand()}
              disabled={isRunning}
            >
              {isRunning ? "Running..." : "Run"}
            </button>
          </div>

          <div className="developer-quick-commands">
            {quickCommands.map((quickCommand) => (
              <button
                key={quickCommand}
                type="button"
                onClick={() => {
                  setCommand(quickCommand);
                  void runCommand(quickCommand);
                }}
                disabled={isRunning}
              >
                {quickCommand}
              </button>
            ))}
          </div>

          <div className="developer-terminal-actions">
            <button type="button" onClick={() => void copyOutput()}>
              Copy Output
            </button>

            <button type="button" onClick={clearOutput}>
              Clear Output
            </button>
          </div>

          <pre className="developer-terminal-output">{output}</pre>
        </section>
      </section>
    </section>
  );
}
