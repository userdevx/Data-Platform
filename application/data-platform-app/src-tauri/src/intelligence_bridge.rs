use std::path::PathBuf;
use std::process::Command;

const DEFAULT_DEFINITION_PATH: &str = "config/intelligence/active.json";

fn data_platform_root() -> Result<PathBuf, String> {
    if let Ok(root) = std::env::var("DATA_PLATFORM_ROOT") {
        let path = PathBuf::from(root);

        if path.exists() {
            return Ok(path);
        }
    }

    let home = std::env::var("HOME")
        .map_err(|error| format!("Could not read HOME environment variable: {error}"))?;

    let path = PathBuf::from(home).join("Data-Platform");

    if path.exists() {
        return Ok(path);
    }

    Err("Data Platform root was not found. Set DATA_PLATFORM_ROOT or use ~/Data-Platform.".to_string())
}

fn python_binary(root: &PathBuf) -> String {
    let venv_python = root.join("venv").join("bin").join("python3");

    if venv_python.exists() {
        return venv_python.to_string_lossy().to_string();
    }

    "python3".to_string()
}

#[tauri::command]
pub fn process_intelligence_request(
    question: String,
    definition: Option<String>,
) -> Result<String, String> {
    let root = data_platform_root()?;
    let python = python_binary(&root);

    let definition_path = definition.unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());

    let output = Command::new(python)
        .current_dir(&root)
        .env("PYTHONPATH", root.to_string_lossy().to_string())
        .arg("-m")
        .arg("app.process_intelligence_request")
        .arg("--json")
        .arg("--definition")
        .arg(definition_path)
        .arg("--source")
        .arg("application_interface")
        .arg(question)
        .output()
        .map_err(|error| format!("Failed to start Intelligence Runtime: {error}"))?;

    if !output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

        if !stdout.is_empty() {
            return Ok(stdout);
        }

        return Err(format!(
            "Intelligence Runtime failed with status {}: {}",
            output.status,
            stderr
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();

    if stdout.is_empty() {
        return Err("Intelligence Runtime returned no output.".to_string());
    }

    Ok(stdout)
}

#[tauri::command]
pub fn get_intelligence_definition(
    definition: Option<String>,
) -> Result<String, String> {
    let root = data_platform_root()?;

    let definition_path = definition.unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());
    let path = root.join(definition_path);

    if !path.exists() {
        return Err(format!(
            "Intelligence Definition was not found: {}",
            path.to_string_lossy()
        ));
    }

    std::fs::read_to_string(path)
        .map_err(|error| format!("Could not read Intelligence Definition: {error}"))
}

#[tauri::command]
pub fn get_data_platform_root() -> Result<String, String> {
    let root = data_platform_root()?;
    Ok(root.to_string_lossy().to_string())
}
