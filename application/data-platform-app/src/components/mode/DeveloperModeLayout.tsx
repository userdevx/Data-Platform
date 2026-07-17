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

type CommandItem = {
  number: number;
  command: string;
  summary: string;
  detail: string;
};

type CommandGroup = {
  title: string;
  commands: CommandItem[];
};

const commandLibrary: CommandGroup[] = [
  {
    title: "Basic Navigation",
    commands: [
      {
        number: 1,
        command: "pwd",
        summary: "Shows the current folder.",
        detail: "Use this to confirm where the Command Terminal is running."
      },
      {
        number: 2,
        command: "ls",
        summary: "Lists files and folders.",
        detail: "Use this to see what exists in the current folder."
      },
      {
        number: 3,
        command: "clear",
        summary: "Clears the terminal output.",
        detail: "This does not delete files or change the project. It only clears what is displayed."
      },
      {
        number: 4,
        command: "cd application/data-platform-app && ls",
        summary: "Lists the application interface files.",
        detail: "Use this to inspect the Tauri application folder."
      }
    ]
  },
  {
    title: "Git",
    commands: [
      {
        number: 1,
        command: "git status --short",
        summary: "Shows changed and untracked files.",
        detail: "Use this before saving work to Git."
      },
      {
        number: 2,
        command: "git log --oneline -5",
        summary: "Shows the five latest commits.",
        detail: "Use this to confirm recent saved checkpoints."
      },
      {
        number: 3,
        command: "git branch --show-current",
        summary: "Shows the active Git branch.",
        detail: "Use this before committing or pushing."
      }
    ]
  },
  {
    title: "Application",
    commands: [
      {
        number: 1,
        command: "cd application/data-platform-app && npm run build",
        summary: "Builds the application interface.",
        detail: "Use this after changing frontend files."
      },
      {
        number: 2,
        command: "cd application/data-platform-app && npm run tauri dev",
        summary: "Starts the Data Platform application.",
        detail: "Use this to open and test the application."
      },
      {
        number: 3,
        command: "cd application/data-platform-app && npm run",
        summary: "Shows available npm scripts.",
        detail: "Use this to see build, dev, preview, and tauri scripts."
      }
    ]
  },
  {
    title: "Rust / Tauri",
    commands: [
      {
        number: 1,
        command: "cd application/data-platform-app/src-tauri && cargo check",
        summary: "Checks the Rust backend.",
        detail: "Use this after changing lib.rs or Tauri command files."
      },
      {
        number: 2,
        command: "rustc --version",
        summary: "Shows the Rust compiler version.",
        detail: "Use this to confirm Rust is installed."
      },
      {
        number: 3,
        command: "cargo --version",
        summary: "Shows the Cargo version.",
        detail: "Use this to confirm Cargo is installed."
      }
    ]
  },
  {
    title: "Python / Data Engine",
    commands: [
      {
        number: 1,
        command: "python3 --version",
        summary: "Shows the Python version.",
        detail: "Use this before running Data Engine scripts."
      },
      {
        number: 2,
        command: "source venv/bin/activate && python -m pytest",
        summary: "Runs the backend test suite.",
        detail: "Use this after changing engine code."
      },
      {
        number: 3,
        command: "source venv/bin/activate && python -m engine.warehouse.build_motion_warehouse",
        summary: "Builds the motion warehouse.",
        detail: "Use this to rebuild stored motion records."
      }
    ]
  },
  {
    title: "Intelligence",
    commands: [
      {
        number: 1,
        command: "tail -n 80 engine/agents/agent.log",
        summary: "Shows recent Intelligence Runtime log output.",
        detail: "Use this when the Intelligence Runtime needs debugging."
      },
      {
        number: 2,
        command: "source venv/bin/activate && python -m engine.agents.agent_worker",
        summary: "Runs the Intelligence Runtime worker.",
        detail: "Use this to start the backend worker."
      },
      {
        number: 3,
        command: "find engine/agents -maxdepth 2 -type f",
        summary: "Lists Intelligence Runtime files.",
        detail: "Use this to inspect worker files, logs, and output files."
      }
    ]
  },
  {
    title: "Logs",
    commands: [
      {
        number: 1,
        command: "ls -la logs",
        summary: "Lists project logs.",
        detail: "Use this to see available log files."
      },
      {
        number: 2,
        command: "find data -maxdepth 3 -type f | head -40",
        summary: "Shows stored data files.",
        detail: "Use this to inspect local data output."
      },
      {
        number: 3,
        command: "find engine -maxdepth 3 -type f | head -60",
        summary: "Shows engine files.",
        detail: "Use this to inspect the Data Engine structure."
      }
    ]
  },
  {
    title: "Processes",
    commands: [
      {
        number: 1,
        command: "ps aux | grep -E 'tauri|vite|python|node' | grep -v grep",
        summary: "Shows running platform processes.",
        detail: "Use this if the app says a port is already in use."
      },
      {
        number: 2,
        command: "pgrep -af 'tauri|vite|python|node'",
        summary: "Shows matching process IDs.",
        detail: "Use this when you need to identify active development processes."
      }
    ]
  },
  {
    title: "Environment",
    commands: [
      {
        number: 1,
        command: "uname -a",
        summary: "Shows operating system details.",
        detail: "Use this to inspect the Linux environment."
      },
      {
        number: 2,
        command: "echo $SHELL",
        summary: "Shows the active shell.",
        detail: "Use this to confirm the shell path."
      },
      {
        number: 3,
        command: "node --version",
        summary: "Shows the Node.js version.",
        detail: "Use this before running npm commands."
      },
      {
        number: 4,
        command: "npm --version",
        summary: "Shows the npm version.",
        detail: "Use this before building the frontend."
      }
    ]
  }
];

const commandGroupsByPage: Record<DeveloperModePage, CommandGroup[]> = {
  Terminal: commandLibrary,
  Git: commandLibrary.filter((group) => group.title === "Git"),
  Build: commandLibrary.filter(
    (group) => group.title === "Application" || group.title === "Rust / Tauri"
  ),
  Tests: commandLibrary.filter((group) => group.title === "Python / Data Engine"),
  Logs: commandLibrary.filter((group) => group.title === "Logs" || group.title === "Intelligence"),
  Processes: commandLibrary.filter((group) => group.title === "Processes"),
  Environment: commandLibrary.filter((group) => group.title === "Environment")
};

function firstCommandForPage(page: DeveloperModePage) {
  return commandGroupsByPage[page][0].commands[0].command;
}

function commandGuideText(groups: CommandGroup[]) {
  const lines: string[] = [];

  lines.push("Command Terminal");
  lines.push("");
  lines.push("Type a command and press Enter.");
  lines.push("");
  lines.push("Built-in:");
  lines.push("  help     Show this command list");
  lines.push("  clear    Clear the terminal output");
  lines.push("");

  for (const group of groups) {
    lines.push(`${group.title}:`);

    for (const item of group.commands) {
      lines.push(`  ${item.number}. ${item.command}`);
      lines.push(`     ${item.summary}`);
      lines.push(`     ${item.detail}`);
      lines.push("");
    }
  }

  return lines.join("\n");
}

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
  const visibleCommandGroups = commandGroupsByPage[activePage];

  const [terminalContext, setTerminalContext] =
    useState<DeveloperTerminalContext | null>(null);

  const [command, setCommand] = useState(firstCommandForPage(activePage));
  const [output, setOutput] = useState(commandGuideText(commandGroupsByPage.Terminal));
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

    if (cleanCommand === "help") {
      setOutput(commandGuideText(visibleCommandGroups));
      setLastStatus("Ready");
      return;
    }

    if (cleanCommand === "clear") {
      setOutput("Terminal cleared. Type help to show commands.");
      setLastStatus("Cleared");
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

  function runCommandOnEnter(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      void runCommand();
    }
  }

  useEffect(() => {
    void loadTerminalContext();
  }, []);

  useEffect(() => {
    setCommand(firstCommandForPage(activePage));
    setOutput(commandGuideText(visibleCommandGroups));
    setLastStatus("Ready");
  }, [activePage]);

  return (
    <section className="developer-mode-layout">
      <aside className="developer-mode-sidebar">
        <div className="developer-mode-brand">
          <div className="developer-mode-logo">⌘</div>

          <div>
            <strong>Developer Mode</strong>
            <span>Development workspace</span>
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
              <h3>Command Terminal</h3>
              <p>Use this workspace to run commands, review output, and inspect the Data Platform.</p>
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

          <div className="developer-terminal-actions">
            <button type="button" onClick={() => void runCommand("help")}>
              Show Commands
            </button>

            <button type="button" onClick={() => void copyOutput()}>
              Copy Output
            </button>

            <button
              type="button"
              onClick={() => {
                setOutput("Terminal cleared. Type help to show commands.");
                setLastStatus("Cleared");
              }}
            >
              Clear Output
            </button>
          </div>

          <pre className="developer-terminal-output">{output}</pre>
        </section>
      </section>
    </section>
  );
}
