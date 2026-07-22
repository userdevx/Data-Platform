use serde::Serialize;
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

static WORKER_STARTED: Mutex<bool> = Mutex::new(false);

#[derive(Serialize)]
pub struct AgentTaskResult {
    success: bool,
    message: String,
    path: String,
}

fn now_timestamp() -> Result<u64, String> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_secs())
}

fn find_project_root() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(current) = std::env::current_dir() {
        let mut dir = current;

        loop {
            candidates.push(dir.clone());

            if !dir.pop() {
                break;
            }
        }
    }

    if let Ok(home) = std::env::var("HOME") {
        candidates.push(PathBuf::from(home).join("Data-Platform"));
    }

    for candidate in candidates {
        let worker = candidate.join("engine").join("agents").join("agent_worker.py");

        if worker.exists() {
            return Ok(candidate);
        }
    }

    Err(
        "Could not find Data-Platform runtime. Expected engine/agents/agent_worker.py."
            .to_string(),
    )
}

fn agent_dir() -> Result<PathBuf, String> {
    let root = find_project_root()?;
    let path = root.join("engine").join("agents");

    fs::create_dir_all(&path).map_err(|error| error.to_string())?;

    Ok(path)
}

fn python_path(root: &PathBuf) -> PathBuf {
    let venv_python = root.join("venv").join("bin").join("python");

    if venv_python.exists() {
        return venv_python;
    }

    PathBuf::from("python3")
}

#[tauri::command]
pub fn start_agent_worker() -> Result<AgentTaskResult, String> {
    let mut started = WORKER_STARTED.lock().map_err(|error| error.to_string())?;

    if *started {
        return Ok(AgentTaskResult {
            success: true,
            message: "Intelligence is already running.".to_string(),
            path: "".to_string(),
        });
    }

    let root = find_project_root()?;
    let agents = agent_dir()?;

    let worker = agents.join("agent_worker.py");
    let log = agents.join("agent.log");
    let python = python_path(&root);

    if !worker.exists() {
        return Err(format!(
            "Agent worker not found at {}",
            worker.to_string_lossy()
        ));
    }

    let log_file = fs::File::create(&log).map_err(|error| error.to_string())?;
    let error_log = log_file.try_clone().map_err(|error| error.to_string())?;

    Command::new(python)
        .arg("-u")
        .arg("-m")
        .arg("engine.agents.agent_worker")
        .current_dir(&root)
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(error_log))
        .spawn()
        .map_err(|error| error.to_string())?;

    *started = true;

    Ok(AgentTaskResult {
        success: true,
        message: "Intelligence started automatically.".to_string(),
        path: log.to_string_lossy().to_string(),
    })
}

#[tauri::command]
pub fn submit_agent_task(input: String) -> Result<AgentTaskResult, String> {
    let agents = agent_dir()?;
    let input_file = agents.join("agent_input.json");

    let clean_input = input.trim();

    if clean_input.is_empty() {
        return Err("Enter a question before submitting.".to_string());
    }

    let payload = json!({
        "input": clean_input,
        "status": "new",
        "timestamp": now_timestamp()?
    });

    fs::write(
        &input_file,
        serde_json::to_string_pretty(&payload).map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;

    Ok(AgentTaskResult {
        success: true,
        message: "Question submitted to the Intelligence Runtime.".to_string(),
        path: input_file.to_string_lossy().to_string(),
    })
}

#[tauri::command]
pub fn read_agent_output() -> Result<String, String> {
    let agents = agent_dir()?;
    let output_file = agents.join("agent_output.json");

    if !output_file.exists() {
        return Err(format!(
            "Agent output file not found yet: {}",
            output_file.to_string_lossy()
        ));
    }

    fs::read_to_string(&output_file).map_err(|error| error.to_string())
}

#[tauri::command]
pub fn read_agent_log() -> Result<String, String> {
    let agents = agent_dir()?;
    let log_file = agents.join("agent.log");

    if !log_file.exists() {
        return Ok("No agent log found yet.".to_string());
    }

    fs::read_to_string(&log_file).map_err(|error| error.to_string())
}
