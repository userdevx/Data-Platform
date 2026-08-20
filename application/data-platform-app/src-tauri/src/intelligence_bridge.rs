use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_DEFINITION_PATH: &str = "config/intelligence/active.json";

const DEFAULT_REQUEST_TIMEOUT_SECONDS: u64 = 60;

const DEFAULT_MAXIMUM_OUTPUT_BYTES: usize = 4 * 1024 * 1024;

const PROCESS_POLL_INTERVAL_MILLISECONDS: u64 = 50;

static AUTOMATIC_REQUEST_RUNNING: AtomicBool = AtomicBool::new(false);

struct AutomaticRequestGuard;

impl AutomaticRequestGuard {
    fn acquire() -> Result<Self, String> {
        AUTOMATIC_REQUEST_RUNNING
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .map_err(|_| "An Automatic intelligence request is already running.".to_string())?;

        Ok(Self)
    }
}

impl Drop for AutomaticRequestGuard {
    fn drop(&mut self) {
        AUTOMATIC_REQUEST_RUNNING.store(false, Ordering::SeqCst);
    }
}

fn application_root() -> Result<PathBuf, String> {
    if let Ok(root) = std::env::var("APPLICATION_ROOT") {
        let path = PathBuf::from(root);

        if application_root_is_valid(&path) {
            return Ok(path);
        }
    }

    if let Ok(current_directory) = std::env::current_dir() {
        let mut candidate = current_directory;

        loop {
            if application_root_is_valid(&candidate) {
                return Ok(candidate);
            }

            if !candidate.pop() {
                break;
            }
        }
    }

    let home = std::env::var("HOME")
        .map_err(|error| format!("Could not read HOME environment variable: {}", error))?;

    let path = PathBuf::from(home).join("Data-Platform");

    if application_root_is_valid(&path) {
        return Ok(path);
    }

    Err(
        "Application root was not found. Set APPLICATION_ROOT to the Data Platform directory."
            .to_string(),
    )
}

fn application_root_is_valid(root: &Path) -> bool {
    root.join("app")
        .join("process_intelligence_request.py")
        .is_file()
        && root.join("config").join("intelligence").is_dir()
}

fn python_binary(root: &Path) -> PathBuf {
    let virtual_environment_python = root.join("venv").join("bin").join("python");

    if virtual_environment_python.is_file() {
        return virtual_environment_python;
    }

    let virtual_environment_python3 = root.join("venv").join("bin").join("python3");

    if virtual_environment_python3.is_file() {
        return virtual_environment_python3;
    }

    PathBuf::from("python3")
}

fn request_timeout() -> Duration {
    let seconds = std::env::var("INTELLIGENCE_REQUEST_TIMEOUT_SECONDS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(DEFAULT_REQUEST_TIMEOUT_SECONDS);

    Duration::from_secs(seconds)
}

fn maximum_output_bytes() -> usize {
    std::env::var("INTELLIGENCE_MAX_OUTPUT_BYTES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(DEFAULT_MAXIMUM_OUTPUT_BYTES)
}

fn read_bounded_stream<R>(
    reader: R,
    maximum_bytes: usize,
    stream_name: &'static str,
) -> Result<Vec<u8>, String>
where
    R: Read,
{
    let read_limit = maximum_bytes.saturating_add(1);

    let mut limited_reader = reader.take(read_limit as u64);

    let mut bytes = Vec::new();

    limited_reader.read_to_end(&mut bytes).map_err(|error| {
        format!(
            "Could not read Intelligence Runtime {}: {}",
            stream_name, error
        )
    })?;

    if bytes.len() > maximum_bytes {
        return Err(format!(
            "Intelligence Runtime {} exceeded the {} byte output limit.",
            stream_name, maximum_bytes
        ));
    }

    Ok(bytes)
}

fn join_stream_reader(
    reader: thread::JoinHandle<Result<Vec<u8>, String>>,
    stream_name: &str,
) -> Result<Vec<u8>, String> {
    reader.join().map_err(|_| {
        format!(
            "The Intelligence Runtime {} reader stopped unexpectedly.",
            stream_name
        )
    })?
}

fn wait_for_process(
    child: &mut std::process::Child,
    timeout: Duration,
) -> Result<ExitStatus, String> {
    let started_at = Instant::now();

    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                return Ok(status);
            }

            Ok(None) => {}

            Err(error) => {
                let _ = child.kill();
                let _ = child.wait();

                return Err(format!(
                    "Could not read Intelligence Runtime process status: {}",
                    error
                ));
            }
        }

        if started_at.elapsed() >= timeout {
            let process_id = child.id();

            let kill_result = child.kill();
            let wait_result = child.wait();

            if let Err(error) = kill_result {
                return Err(format!(
                    "Intelligence Runtime exceeded its {} second timeout, but process {} could not be terminated: {}",
                    timeout.as_secs(),
                    process_id,
                    error
                ));
            }

            if let Err(error) = wait_result {
                return Err(format!(
                    "Intelligence Runtime exceeded its {} second timeout. Process {} was terminated, but cleanup failed: {}",
                    timeout.as_secs(),
                    process_id,
                    error
                ));
            }

            return Err(format!(
                "Intelligence Runtime exceeded its {} second timeout and was terminated.",
                timeout.as_secs()
            ));
        }

        thread::sleep(Duration::from_millis(PROCESS_POLL_INTERVAL_MILLISECONDS));
    }
}

fn run_intelligence_request(
    question: String,
    definition: Option<String>,
    conversation_id: Option<String>,
) -> Result<String, String> {
    let root = application_root()?;

    let definition_path = definition.unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());

    let timeout = request_timeout();
    let output_limit = maximum_output_bytes();

    let python = python_binary(&root);

    let mut command = Command::new("nice");

    command
        .arg("-n")
        .arg("10")
        .arg(python)
        .current_dir(&root)
        .env("PYTHONPATH", &root)
        .env("PYTHONUNBUFFERED", "1")
        .env("OMP_NUM_THREADS", "2")
        .env("OPENBLAS_NUM_THREADS", "2")
        .env("MKL_NUM_THREADS", "2")
        .env("NUMEXPR_NUM_THREADS", "2")
        .env("TOKENIZERS_PARALLELISM", "false")
        .env("OLLAMA_NUM_PARALLEL", "1")
        .env("OLLAMA_MAX_LOADED_MODELS", "1")
        .arg("-m")
        .arg("app.process_intelligence_request")
        .arg("--json")
        .arg("--definition")
        .arg(definition_path)
        .arg("--source")
        .arg("application_interface");

    if let Some(conversation_id) = conversation_id
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
    {
        command
            .arg("--conversation-id")
            .arg(conversation_id);
    }

    let mut child = command
        .arg(question)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| format!("Failed to start Intelligence Runtime: {}", error))?;

    let stdout = child.stdout.take().ok_or_else(|| {
        let _ = child.kill();
        let _ = child.wait();

        "Intelligence Runtime stdout was unavailable.".to_string()
    })?;

    let stderr = child.stderr.take().ok_or_else(|| {
        let _ = child.kill();
        let _ = child.wait();

        "Intelligence Runtime stderr was unavailable.".to_string()
    })?;

    let stdout_reader = thread::spawn(move || read_bounded_stream(stdout, output_limit, "stdout"));

    let stderr_reader = thread::spawn(move || read_bounded_stream(stderr, output_limit, "stderr"));

    let process_result = wait_for_process(&mut child, timeout);

    let stdout_result = join_stream_reader(stdout_reader, "stdout");

    let stderr_result = join_stream_reader(stderr_reader, "stderr");

    let status = process_result?;
    let stdout_bytes = stdout_result?;
    let stderr_bytes = stderr_result?;

    let stdout_text = String::from_utf8_lossy(&stdout_bytes).trim().to_string();

    let stderr_text = String::from_utf8_lossy(&stderr_bytes).trim().to_string();

    if !status.success() {
        /*
         * Preserve the existing Python contract:
         * the runtime may return a structured JSON
         * failure through stdout.
         */
        if !stdout_text.is_empty() {
            return Ok(stdout_text);
        }

        if !stderr_text.is_empty() {
            return Err(format!(
                "Intelligence Runtime failed with status {}: {}",
                status, stderr_text
            ));
        }

        return Err(format!(
            "Intelligence Runtime failed with status {} and returned no diagnostic output.",
            status
        ));
    }

    if stdout_text.is_empty() {
        if !stderr_text.is_empty() {
            return Err(format!(
                "Intelligence Runtime returned no output. Diagnostic: {}",
                stderr_text
            ));
        }

        return Err("Intelligence Runtime returned no output.".to_string());
    }

    Ok(stdout_text)
}

#[tauri::command]
pub async fn process_intelligence_request(
    question: String,
    definition: Option<String>,
    conversation_id: Option<String>,
) -> Result<String, String> {
    /*
     * Acquire this before starting the worker so
     * duplicate Automatic requests are rejected
     * immediately.
     */
    let request_guard = AutomaticRequestGuard::acquire()?;

    tauri::async_runtime::spawn_blocking(move || {
        let _request_guard = request_guard;

        run_intelligence_request(
            question,
            definition,
            conversation_id,
        )
    })
    .await
    .map_err(|error| format!("The Automatic intelligence worker task failed: {}", error))?
}

#[tauri::command]
pub async fn update_memory_settings(
    definition: Option<String>,
    enabled: bool,
    read: bool,
    write: bool,
    automatic_recall: bool,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let root = application_root()?;

        let definition_path = definition
            .unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());

        let path = root.join(&definition_path);

        if !path.is_file() {
            return Err(format!(
                "Intelligence Definition was not found: {}",
                path.to_string_lossy()
            ));
        }

        let canonical_root = root
            .canonicalize()
            .map_err(|error| {
                format!(
                    "Could not resolve the application root: {}",
                    error
                )
            })?;

        let canonical_path = path
            .canonicalize()
            .map_err(|error| {
                format!(
                    "Could not resolve the Intelligence Definition: {}",
                    error
                )
            })?;

        if !canonical_path.starts_with(&canonical_root) {
            return Err(
                "The Intelligence Definition must be inside the application root."
                    .to_string()
            );
        }

        let raw = std::fs::read_to_string(&canonical_path)
            .map_err(|error| {
                format!(
                    "Could not read the Intelligence Definition: {}",
                    error
                )
            })?;

        let mut definition_value:
            serde_json::Value =
            serde_json::from_str(&raw)
                .map_err(|error| {
                    format!(
                        "The Intelligence Definition contains invalid JSON: {}",
                        error
                    )
                })?;

        let root_object = definition_value
            .as_object_mut()
            .ok_or_else(|| {
                "The Intelligence Definition must be a JSON object."
                    .to_string()
            })?;

        let memory_value = root_object
            .entry("memory")
            .or_insert_with(|| {
                serde_json::json!({})
            });

        let memory = memory_value
            .as_object_mut()
            .ok_or_else(|| {
                "The memory configuration must be a JSON object."
                    .to_string()
            })?;

        memory.insert(
            "enabled".to_string(),
            serde_json::Value::Bool(enabled),
        );

        memory.insert(
            "read".to_string(),
            serde_json::Value::Bool(read),
        );

        memory.insert(
            "write".to_string(),
            serde_json::Value::Bool(write),
        );

        memory.insert(
            "automatic_recall".to_string(),
            serde_json::Value::Bool(
                automatic_recall,
            ),
        );

        /*
         * Preserve the existing memory configuration fields,
         * including source, storage_owner, and context_budget.
         * Only the behavior controls above are changed.
         */

        let formatted =
            serde_json::to_string_pretty(
                &definition_value
            )
            .map_err(|error| {
                format!(
                    "Could not serialize the Intelligence Definition: {}",
                    error
                )
            })?;

        let parent = canonical_path
            .parent()
            .ok_or_else(|| {
                "The Intelligence Definition has no parent directory."
                    .to_string()
            })?;

        let file_name = canonical_path
            .file_name()
            .and_then(|value| value.to_str())
            .ok_or_else(|| {
                "The Intelligence Definition filename is invalid."
                    .to_string()
            })?;

        let temporary_path = parent.join(
            format!(
                ".{}.memory-update.tmp",
                file_name
            )
        );

        std::fs::write(
            &temporary_path,
            format!("{}\n", formatted),
        )
        .map_err(|error| {
            format!(
                "Could not write the temporary Intelligence Definition: {}",
                error
            )
        })?;

        std::fs::rename(
            &temporary_path,
            &canonical_path,
        )
        .map_err(|error| {
            let _ = std::fs::remove_file(
                &temporary_path
            );

            format!(
                "Could not activate the updated Intelligence Definition: {}",
                error
            )
        })?;

        Ok(
            serde_json::json!({
                "status": "success",
                "memory": {
                    "enabled": enabled,
                    "read": read,
                    "write": write,
                    "automatic_recall":
                        automatic_recall,
                }
            })
            .to_string()
        )
    })
    .await
    .map_err(|error| {
        format!(
            "The memory configuration worker task failed: {}",
            error
        )
    })?
}


#[tauri::command]
pub async fn update_permission_settings(
    definition: Option<String>,
    read_records: bool,
    write_records: bool,
    write_history: bool,
    run_approved_commands: bool,
    network_access: bool,
    modify_system_files: bool,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let root = application_root()?;

        let definition_path = definition
            .unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());

        let path = root.join(&definition_path);

        if !path.is_file() {
            return Err(format!(
                "Intelligence Definition was not found: {}",
                path.to_string_lossy()
            ));
        }

        let canonical_root = root
            .canonicalize()
            .map_err(|error| {
                format!(
                    "Could not resolve the application root: {}",
                    error
                )
            })?;

        let canonical_path = path
            .canonicalize()
            .map_err(|error| {
                format!(
                    "Could not resolve the Intelligence Definition: {}",
                    error
                )
            })?;

        if !canonical_path.starts_with(&canonical_root) {
            return Err(
                "The Intelligence Definition must be inside the application root."
                    .to_string()
            );
        }

        let raw = std::fs::read_to_string(&canonical_path)
            .map_err(|error| {
                format!(
                    "Could not read the Intelligence Definition: {}",
                    error
                )
            })?;

        let mut definition_value: serde_json::Value =
            serde_json::from_str(&raw)
                .map_err(|error| {
                    format!(
                        "The Intelligence Definition contains invalid JSON: {}",
                        error
                    )
                })?;

        let root_object = definition_value
            .as_object_mut()
            .ok_or_else(|| {
                "The Intelligence Definition must be a JSON object."
                    .to_string()
            })?;

        let permissions_value = root_object
            .entry("permissions")
            .or_insert_with(|| {
                serde_json::json!({})
            });

        let permissions = permissions_value
            .as_object_mut()
            .ok_or_else(|| {
                "The permissions configuration must be a JSON object."
                    .to_string()
            })?;

        permissions.insert(
            "read_records".to_string(),
            serde_json::Value::Bool(read_records),
        );

        permissions.insert(
            "write_records".to_string(),
            serde_json::Value::Bool(write_records),
        );

        permissions.insert(
            "write_history".to_string(),
            serde_json::Value::Bool(write_history),
        );

        permissions.insert(
            "run_approved_commands".to_string(),
            serde_json::Value::Bool(run_approved_commands),
        );

        permissions.insert(
            "network_access".to_string(),
            serde_json::Value::Bool(network_access),
        );

        permissions.insert(
            "modify_system_files".to_string(),
            serde_json::Value::Bool(modify_system_files),
        );

        let formatted =
            serde_json::to_string_pretty(
                &definition_value
            )
            .map_err(|error| {
                format!(
                    "Could not serialize the Intelligence Definition: {}",
                    error
                )
            })?;

        let parent = canonical_path
            .parent()
            .ok_or_else(|| {
                "The Intelligence Definition has no parent directory."
                    .to_string()
            })?;

        let file_name = canonical_path
            .file_name()
            .and_then(|value| value.to_str())
            .ok_or_else(|| {
                "The Intelligence Definition filename is invalid."
                    .to_string()
            })?;

        let temporary_path = parent.join(
            format!(
                ".{}.permissions-update.tmp",
                file_name
            )
        );

        std::fs::write(
            &temporary_path,
            format!("{}\n", formatted),
        )
        .map_err(|error| {
            format!(
                "Could not write the temporary Intelligence Definition: {}",
                error
            )
        })?;

        std::fs::rename(
            &temporary_path,
            &canonical_path,
        )
        .map_err(|error| {
            let _ = std::fs::remove_file(
                &temporary_path
            );

            format!(
                "Could not activate the updated Intelligence Definition: {}",
                error
            )
        })?;

        Ok(
            serde_json::json!({
                "status": "success",
                "permissions": {
                    "read_records": read_records,
                    "write_records": write_records,
                    "write_history": write_history,
                    "run_approved_commands":
                        run_approved_commands,
                    "network_access": network_access,
                    "modify_system_files":
                        modify_system_files,
                }
            })
            .to_string()
        )
    })
    .await
    .map_err(|error| {
        format!(
            "The permission configuration worker task failed: {}",
            error
        )
    })?
}


#[tauri::command]
pub async fn update_personalization_settings(
    definition: Option<String>,
    display_name: String,
    role: String,
    description: String,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let root = application_root()?;

        let definition_path = definition
            .unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());

        let path = root.join(&definition_path);

        if !path.is_file() {
            return Err(format!(
                "Intelligence Definition was not found: {}",
                path.to_string_lossy()
            ));
        }

        let canonical_root = root
            .canonicalize()
            .map_err(|error| {
                format!(
                    "Could not resolve the application root: {}",
                    error
                )
            })?;

        let canonical_path = path
            .canonicalize()
            .map_err(|error| {
                format!(
                    "Could not resolve the Intelligence Definition: {}",
                    error
                )
            })?;

        if !canonical_path.starts_with(&canonical_root) {
            return Err(
                "The Intelligence Definition must be inside the application root."
                    .to_string()
            );
        }

        let clean_display_name =
            display_name.trim().to_string();

        let clean_role =
            role.trim().to_string();

        let clean_description =
            description.trim().to_string();

        if clean_display_name.is_empty() {
            return Err(
                "Display name cannot be empty."
                    .to_string()
            );
        }

        if clean_role.is_empty() {
            return Err(
                "Role cannot be empty."
                    .to_string()
            );
        }

        if clean_description.is_empty() {
            return Err(
                "Description cannot be empty."
                    .to_string()
            );
        }

        let raw =
            std::fs::read_to_string(
                &canonical_path
            )
            .map_err(|error| {
                format!(
                    "Could not read the Intelligence Definition: {}",
                    error
                )
            })?;

        let mut definition_value:
            serde_json::Value =
            serde_json::from_str(&raw)
                .map_err(|error| {
                    format!(
                        "The Intelligence Definition contains invalid JSON: {}",
                        error
                    )
                })?;

        let root_object =
            definition_value
                .as_object_mut()
                .ok_or_else(|| {
                    "The Intelligence Definition must be a JSON object."
                        .to_string()
                })?;

        let identity_value =
            root_object
                .get_mut("identity")
                .ok_or_else(|| {
                    "The Intelligence Definition is missing identity configuration."
                        .to_string()
                })?;

        let identity =
            identity_value
                .as_object_mut()
                .ok_or_else(|| {
                    "The identity configuration must be a JSON object."
                        .to_string()
                })?;

        /*
         * Preserve stable internal identity fields:
         *
         * identity.id
         * identity.name
         *
         * Only user-configurable presentation fields
         * are updated.
         */

        identity.insert(
            "display_name".to_string(),
            serde_json::Value::String(
                clean_display_name.clone()
            ),
        );

        identity.insert(
            "role".to_string(),
            serde_json::Value::String(
                clean_role.clone()
            ),
        );

        identity.insert(
            "description".to_string(),
            serde_json::Value::String(
                clean_description.clone()
            ),
        );

        let formatted =
            serde_json::to_string_pretty(
                &definition_value
            )
            .map_err(|error| {
                format!(
                    "Could not serialize the Intelligence Definition: {}",
                    error
                )
            })?;

        let parent =
            canonical_path
                .parent()
                .ok_or_else(|| {
                    "The Intelligence Definition has no parent directory."
                        .to_string()
                })?;

        let file_name =
            canonical_path
                .file_name()
                .and_then(
                    |value| value.to_str()
                )
                .ok_or_else(|| {
                    "The Intelligence Definition filename is invalid."
                        .to_string()
                })?;

        let temporary_path =
            parent.join(
                format!(
                    ".{}.personalization-update.tmp",
                    file_name
                )
            );

        std::fs::write(
            &temporary_path,
            format!("{}\n", formatted),
        )
        .map_err(|error| {
            format!(
                "Could not write the temporary Intelligence Definition: {}",
                error
            )
        })?;

        std::fs::rename(
            &temporary_path,
            &canonical_path,
        )
        .map_err(|error| {
            let _ =
                std::fs::remove_file(
                    &temporary_path
                );

            format!(
                "Could not activate the updated Intelligence Definition: {}",
                error
            )
        })?;

        Ok(
            serde_json::json!({
                "status": "success",
                "personalization": {
                    "display_name":
                        clean_display_name,
                    "role":
                        clean_role,
                    "description":
                        clean_description,
                }
            })
            .to_string()
        )
    })
    .await
    .map_err(|error| {
        format!(
            "The personalization configuration worker task failed: {}",
            error
        )
    })?
}


#[tauri::command]
pub async fn get_intelligence_definition(definition: Option<String>) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let root = application_root()?;

        let definition_path = definition.unwrap_or_else(|| DEFAULT_DEFINITION_PATH.to_string());

        let path = root.join(definition_path);

        if !path.is_file() {
            return Err(format!(
                "Intelligence Definition was not found: {}",
                path.to_string_lossy()
            ));
        }

        let metadata = std::fs::metadata(&path)
            .map_err(|error| format!("Could not inspect Intelligence Definition: {}", error))?;

        if metadata.len() > DEFAULT_MAXIMUM_OUTPUT_BYTES as u64 {
            return Err(format!(
                "Intelligence Definition exceeded the {} byte limit.",
                DEFAULT_MAXIMUM_OUTPUT_BYTES
            ));
        }

        std::fs::read_to_string(path)
            .map_err(|error| format!("Could not read Intelligence Definition: {}", error))
    })
    .await
    .map_err(|error| format!("The Intelligence Definition worker task failed: {}", error))?
}

#[tauri::command]
pub fn get_application_root() -> Result<String, String> {
    let root = application_root()?;

    Ok(root.to_string_lossy().to_string())
}
