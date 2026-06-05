use serde::Serialize;
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

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
    let mut dir = std::env::current_dir().map_err(|error| error.to_string())?;

    loop {
        let worker = dir.join("engine").join("agents").join("agent_worker.py");

        if worker.exists() {
            return Ok(dir);
        }

        if !dir.pop() {
            return Err(
                "Could not find Data-Platform project root. Expected engine/agents/agent_worker.py."
                    .to_string(),
            );
        }
    }
}

fn agent_dir() -> Result<PathBuf, String> {
    let root = find_project_root()?;
    let path = root.join("engine").join("agents");

    fs::create_dir_all(&path).map_err(|error| error.to_string())?;

    Ok(path)
}

#[tauri::command]
pub fn start_agent_worker() -> Result<AgentTaskResult, String> {
    let root = find_project_root()?;
    let agents = agent_dir()?;

    let worker = agents.join("agent_worker.py");
    let log = agents.join("agent.log");

    if !worker.exists() {
        return Err(format!(
            "Agent worker not found at {}",
            worker.to_string_lossy()
        ));
    }

    let log_file = fs::File::create(&log).map_err(|error| error.to_string())?;

    Command::new("python3")
        .arg("-u")
        .arg(&worker)
        .current_dir(&root)
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| error.to_string())?;

    Ok(AgentTaskResult {
        success: true,
        message: "Agent worker started.".to_string(),
        path: log.to_string_lossy().to_string(),
    })
}

#[tauri::command]
pub fn submit_agent_task(input: String) -> Result<AgentTaskResult, String> {
    let agents = agent_dir()?;
    let input_file = agents.join("agent_input.json");

    let clean_input = input.trim();

    if clean_input.is_empty() {
        return Err("Enter a question before asking the agent.".to_string());
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
        message: "Task submitted to agent.".to_string(),
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
