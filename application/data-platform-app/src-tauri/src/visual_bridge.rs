use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VisualBridgeResponse {
    pub status: String,
    pub answer: String,
    pub data: Value,
    pub errors: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnalyzeVisualImageRequest {
    pub image_path: String,
    pub query: String,
    pub source_reference: Option<String>,
}

fn project_root() -> Result<PathBuf, String> {
    let manifest_directory = PathBuf::from(env!("CARGO_MANIFEST_DIR"));

    manifest_directory
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .ok_or_else(|| "The Data Platform project root could not be resolved.".to_string())
}

fn python_executable(root: &Path) -> PathBuf {
    root.join("venv").join("bin").join("python")
}

fn visual_configuration(root: &Path) -> PathBuf {
    root.join("config").join("vision").join("active.json")
}

fn execute_visual_bridge(arguments: &[String]) -> Result<VisualBridgeResponse, String> {
    let root = project_root()?;
    let python = python_executable(&root);

    if !python.is_file() {
        return Err("The configured Python interpreter was not found.".to_string());
    }

    let mut command = Command::new(&python);

    command
        .current_dir(&root)
        .env("PYTHONPATH", &root)
        .arg("-m")
        .arg("engine.intelligence.vision.application_bridge");

    for argument in arguments {
        command.arg(argument);
    }

    let output = command
        .output()
        .map_err(|error| format!("The visual bridge could not be started: {error}"))?;

    let stdout = String::from_utf8(output.stdout)
        .map_err(|error| format!("The visual bridge returned invalid text: {error}"))?;

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if stdout.trim().is_empty() {
        return Err(if stderr.is_empty() {
            "The visual bridge returned no response.".to_string()
        } else {
            stderr
        });
    }

    serde_json::from_str::<VisualBridgeResponse>(stdout.trim())
        .map_err(|error| format!("The visual bridge returned invalid JSON: {error}"))
}

#[tauri::command]
pub fn get_visual_runtime_status() -> Result<VisualBridgeResponse, String> {
    let root = project_root()?;
    let configuration = visual_configuration(&root);

    execute_visual_bridge(&[
        "status".to_string(),
        "--configuration".to_string(),
        configuration.to_string_lossy().to_string(),
    ])
}

#[tauri::command]
pub fn analyze_visual_image(
    request: AnalyzeVisualImageRequest,
) -> Result<VisualBridgeResponse, String> {
    let image_path = request.image_path.trim();

    let query = request.query.trim();

    if image_path.is_empty() {
        return Err("An image path is required.".to_string());
    }

    if query.is_empty() {
        return Err("A visual-analysis question is required.".to_string());
    }

    let root = project_root()?;
    let configuration = visual_configuration(&root);

    let mut arguments = vec![
        "analyze-image".to_string(),
        "--image-path".to_string(),
        image_path.to_string(),
        "--query".to_string(),
        query.to_string(),
        "--configuration".to_string(),
        configuration.to_string_lossy().to_string(),
    ];

    if let Some(source_reference) = request.source_reference {
        let clean_reference = source_reference.trim();

        if !clean_reference.is_empty() {
            arguments.push("--source-reference".to_string());

            arguments.push(clean_reference.to_string());
        }
    }

    execute_visual_bridge(&arguments)
}
