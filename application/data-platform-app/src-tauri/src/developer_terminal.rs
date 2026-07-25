use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Deserialize)]
pub struct DeveloperTerminalRequest {
    command: String,
}

#[derive(Serialize)]
pub struct DeveloperTerminalResponse {
    success: bool,
    command: String,
    working_directory: String,
    shell: String,
    exit_code: Option<i32>,
    stdout: String,
    stderr: String,
    suggestion: String,
    message: String,
    timestamp: u64,
}

#[derive(Serialize)]
pub struct DeveloperTerminalContext {
    working_directory: String,
    operating_system: String,
    shell: String,
    project_root_found: bool,
    message: String,
}

fn timestamp() -> Result<u64, String> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_secs())
}

fn find_project_root() -> Result<PathBuf, String> {
    let mut directory = std::env::current_dir().map_err(|error| error.to_string())?;

    loop {
        let app_folder = directory.join("application").join("data-platform-app");
        let engine_folder = directory.join("engine");

        if app_folder.exists() && engine_folder.exists() {
            return Ok(directory);
        }

        if !directory.pop() {
            return std::env::current_dir().map_err(|error| error.to_string());
        }
    }
}

fn detect_shell() -> String {
    if cfg!(target_os = "windows") {
        return std::env::var("COMSPEC").unwrap_or_else(|_| "cmd.exe".to_string());
    }

    std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".to_string())
}

fn run_shell_command(
    command: &str,
    working_directory: &PathBuf,
) -> Result<std::process::Output, String> {
    if cfg!(target_os = "windows") {
        Command::new("cmd")
            .arg("/C")
            .arg(command)
            .current_dir(working_directory)
            .output()
            .map_err(|error| error.to_string())
    } else {
        Command::new("bash")
            .arg("-lc")
            .arg(command)
            .current_dir(working_directory)
            .output()
            .map_err(|error| error.to_string())
    }
}

fn command_suggestion(command: &str, stdout: &str, stderr: &str, exit_code: Option<i32>) -> String {
    let combined = format!("{}\n{}", stdout, stderr).to_lowercase();
    let command_lower = command.to_lowercase();

    if exit_code == Some(0) {
        return "Command completed successfully.".to_string();
    }

    if combined.contains("permission denied") {
        return format!(
            "This command may require administrator permission. Try: sudo {}",
            command
        );
    }

    if combined.contains("command not found") {
        if command_lower.starts_with("python ") {
            return "Python command was not found. Try: python3 instead.".to_string();
        }

        if command_lower.starts_with("node ") {
            return "Node.js was not found. Install Node.js or check your PATH.".to_string();
        }

        if command_lower.starts_with("npm ") {
            return "npm was not found. Install Node.js/npm or check your PATH.".to_string();
        }

        if command_lower.starts_with("cargo ") {
            return "Cargo was not found. Install Rust with rustup or check your PATH.".to_string();
        }

        return "Command not found. Check the spelling or install the missing tool.".to_string();
    }

    if combined.contains("port 1420 is already in use") {
        return "Port 1420 is already in use. Stop the running Vite/Tauri process with CTRL + C, then run again.".to_string();
    }

    if combined.contains("expected `,`") || combined.contains("expected `;`") {
        return "Rust syntax error. Check the line before the reported line for a missing comma, bracket, or semicolon.".to_string();
    }

    if combined.contains("could not compile") {
        return "The Rust backend failed to compile. Review the first error above, fix it, then run cargo check again.".to_string();
    }

    if combined.contains("tsc") && combined.contains("error") {
        return "TypeScript build failed. Review the first TypeScript error and fix the referenced file.".to_string();
    }

    if combined.contains("no such file or directory") {
        return "The file or folder does not exist. Check the path and run pwd or ls to confirm your location.".to_string();
    }

    if combined.contains("not a git repository") {
        return "This folder is not a Git repository. Move to the project root or check the working directory.".to_string();
    }

    "Command finished with an error. Review stderr above and retry.".to_string()
}

fn append_terminal_history(record: &DeveloperTerminalResponse) -> Result<(), String> {
    let root = find_project_root()?;
    let history_path = root
        .join("data")
        .join("developer")
        .join("terminal_history.jsonl");

    if let Some(parent) = history_path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }

    let json = serde_json::to_string(record).map_err(|error| error.to_string())?;

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(history_path)
        .map_err(|error| error.to_string())?;

    writeln!(file, "{}", json).map_err(|error| error.to_string())?;

    Ok(())
}

#[tauri::command]
pub fn get_developer_terminal_context() -> Result<DeveloperTerminalContext, String> {
    let root = find_project_root()?;
    let shell = detect_shell();

    Ok(DeveloperTerminalContext {
        working_directory: root.to_string_lossy().to_string(),
        operating_system: std::env::consts::OS.to_string(),
        shell,
        project_root_found: true,
        message: "Developer terminal context loaded.".to_string(),
    })
}

#[tauri::command]
pub fn run_developer_terminal_command(
    request: DeveloperTerminalRequest,
) -> Result<DeveloperTerminalResponse, String> {
    let command = request.command.trim().to_string();

    if command.is_empty() {
        return Err("Enter a command first.".to_string());
    }

    let root = find_project_root()?;
    let shell = detect_shell();
    let command_output = run_shell_command(&command, &root)?;
    let exit_code = command_output.status.code();

    let stdout = String::from_utf8_lossy(&command_output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&command_output.stderr).to_string();
    let success = command_output.status.success();

    let suggestion = command_suggestion(&command, &stdout, &stderr, exit_code);

    let response = DeveloperTerminalResponse {
        success,
        command,
        working_directory: root.to_string_lossy().to_string(),
        shell,
        exit_code,
        stdout,
        stderr,
        suggestion,
        message: if success {
            "Command completed.".to_string()
        } else {
            "Command finished with an error.".to_string()
        },
        timestamp: timestamp()?,
    };

    append_terminal_history(&response)?;

    Ok(response)
}
