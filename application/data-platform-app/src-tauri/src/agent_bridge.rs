use serde::Serialize;
use serde_json::json;
use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

static WORKER_PROCESS: Mutex<Option<Child>> = Mutex::new(None);

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

    for variable in ["DATA_PLATFORM_ROOT", "APPLICATION_ROOT"] {
        if let Ok(value) = std::env::var(variable) {
            let value = value.trim();

            if !value.is_empty() {
                candidates.push(PathBuf::from(value));
            }
        }
    }

    if let Ok(home) = std::env::var("HOME") {
        candidates.push(PathBuf::from(home).join("Data-Platform"));
    }

    if let Ok(current) = std::env::current_dir() {
        let mut directory = current;

        loop {
            candidates.push(directory.clone());

            if !directory.pop() {
                break;
            }
        }
    }

    for candidate in candidates {
        if candidate
            .join("engine")
            .join("agents")
            .join("agent_worker.py")
            .is_file()
        {
            return Ok(candidate);
        }
    }

    Err(
        "Could not find Data-Platform runtime. Set DATA_PLATFORM_ROOT or APPLICATION_ROOT."
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
    let mut worker_process = WORKER_PROCESS.lock().map_err(|error| error.to_string())?;

    if let Some(child) = worker_process.as_mut() {
        match child.try_wait() {
            Ok(None) => {
                return Ok(AgentTaskResult {
                    success: true,
                    message: format!(
                        "Intelligence worker is already running (PID {}).",
                        child.id(),
                    ),
                    path: String::new(),
                });
            }
            Ok(Some(_)) => {
                *worker_process = None;
            }
            Err(error) => {
                return Err(format!("Unable to inspect Intelligence worker: {}", error,));
            }
        }
    }

    let root = find_project_root()?;
    let agents = agent_dir()?;

    let worker = agents.join("agent_worker.py");
    let log = agents.join("agent.log");
    let python = python_path(&root);

    if !worker.exists() {
        return Err(format!(
            "Agent worker not found at {}",
            worker.to_string_lossy(),
        ));
    }

    let log_file = fs::File::create(&log).map_err(|error| error.to_string())?;

    let error_log = log_file.try_clone().map_err(|error| error.to_string())?;

    let child = Command::new(python)
        .arg("-u")
        .arg("-m")
        .arg("engine.agents.agent_worker")
        .current_dir(&root)
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(error_log))
        .spawn()
        .map_err(|error| format!("Unable to start Intelligence worker: {}", error,))?;

    let pid = child.id();

    *worker_process = Some(child);

    Ok(AgentTaskResult {
        success: true,
        message: format!("Intelligence worker started (PID {}).", pid,),
        path: log.to_string_lossy().to_string(),
    })
}

pub fn stop_agent_worker() -> Result<(), String> {
    let mut worker_process = WORKER_PROCESS.lock().map_err(|error| error.to_string())?;

    let Some(mut child) = worker_process.take() else {
        return Ok(());
    };

    match child.try_wait() {
        Ok(Some(_)) => Ok(()),
        Ok(None) => {
            child
                .kill()
                .map_err(|error| format!("Unable to stop Intelligence worker: {}", error,))?;

            child.wait().map_err(|error| {
                format!("Unable to wait for Intelligence worker shutdown: {}", error,)
            })?;

            Ok(())
        }
        Err(error) => Err(format!(
            "Unable to inspect Intelligence worker during shutdown: {}",
            error,
        )),
    }
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
        "timestamp": now_timestamp()?,
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
            output_file.to_string_lossy(),
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
