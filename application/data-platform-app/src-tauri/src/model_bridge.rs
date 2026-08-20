use std::io::{self, Read};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread;
use std::time::{Duration, Instant};

const MODEL_BRIDGE_MODULE: &str = "engine.application.tauri_model_bridge";

const DEFAULT_OPTIONS_TIMEOUT_SECONDS: u64 = 15;
const DEFAULT_REQUEST_TIMEOUT_SECONDS: u64 = 60;
const DEFAULT_MAX_OUTPUT_BYTES: usize = 4 * 1024 * 1024;

static REQUEST_RUNNING: AtomicBool = AtomicBool::new(false);

static CANCEL_REQUESTED: AtomicBool = AtomicBool::new(false);

static ACTIVE_CHILD: OnceLock<Mutex<Option<Arc<Mutex<Child>>>>> = OnceLock::new();

fn active_child() -> &'static Mutex<Option<Arc<Mutex<Child>>>> {
    ACTIVE_CHILD.get_or_init(|| Mutex::new(None))
}

struct RequestGuard;

impl RequestGuard {
    fn acquire() -> Result<Self, String> {
        REQUEST_RUNNING
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .map_err(|_| "A model request is already running.".to_string())?;

        CANCEL_REQUESTED.store(false, Ordering::SeqCst);

        Ok(Self)
    }
}

impl Drop for RequestGuard {
    fn drop(&mut self) {
        REQUEST_RUNNING.store(false, Ordering::SeqCst);

        CANCEL_REQUESTED.store(false, Ordering::SeqCst);
    }
}

fn application_root() -> Result<PathBuf, String> {
    if let Ok(configured_root) = std::env::var("APPLICATION_ROOT") {
        let path = PathBuf::from(configured_root);

        if model_bridge_exists(&path) {
            return Ok(path);
        }
    }

    if let Ok(current_directory) = std::env::current_dir() {
        let mut candidate = current_directory;

        loop {
            if model_bridge_exists(&candidate) {
                return Ok(candidate);
            }

            if !candidate.pop() {
                break;
            }
        }
    }

    if let Ok(home_directory) = std::env::var("HOME") {
        let candidate = PathBuf::from(home_directory).join("Data-Platform");

        if model_bridge_exists(&candidate) {
            return Ok(candidate);
        }
    }

    Err("The application model bridge could not be found.".to_string())
}

fn model_bridge_exists(root: &Path) -> bool {
    root.join("engine")
        .join("application")
        .join("tauri_model_bridge.py")
        .is_file()
}

fn python_binary(root: &Path) -> PathBuf {
    let virtual_environment_python = root.join("venv").join("bin").join("python");

    if virtual_environment_python.is_file() {
        virtual_environment_python
    } else {
        PathBuf::from("python3")
    }
}

fn read_environment_u64(name: &str, default_value: u64) -> u64 {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(default_value)
}

fn read_environment_usize(name: &str, default_value: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(default_value)
}

fn read_pipe<R>(mut reader: R) -> io::Result<Vec<u8>>
where
    R: Read,
{
    let mut bytes = Vec::new();
    reader.read_to_end(&mut bytes)?;
    Ok(bytes)
}

fn store_active_child(child: Arc<Mutex<Child>>) -> Result<(), String> {
    let mut active = active_child()
        .lock()
        .map_err(|_| "The worker state lock is unavailable.".to_string())?;

    *active = Some(child);

    Ok(())
}

fn clear_active_child(child: &Arc<Mutex<Child>>) {
    if let Ok(mut active) = active_child().lock() {
        let should_clear = active
            .as_ref()
            .map(|current| Arc::ptr_eq(current, child))
            .unwrap_or(false);

        if should_clear {
            *active = None;
        }
    }
}

fn terminate_child(child: &Arc<Mutex<Child>>) {
    if let Ok(mut process) = child.lock() {
        let _ = process.kill();
        let _ = process.wait();
    }
}

fn wait_for_child(
    child: &Arc<Mutex<Child>>,
    timeout: Duration,
) -> Result<std::process::ExitStatus, String> {
    let started_at = Instant::now();

    loop {
        if CANCEL_REQUESTED.load(Ordering::SeqCst) {
            terminate_child(child);

            return Err("The request was cancelled.".to_string());
        }

        if started_at.elapsed() >= timeout {
            terminate_child(child);

            return Err(format!(
                "The operation exceeded its {} second timeout.",
                timeout.as_secs(),
            ));
        }

        let status = {
            let mut process = child
                .lock()
                .map_err(|_| "The worker process lock is unavailable.".to_string())?;

            process.try_wait().map_err(|error| {
                format!("The worker process status could not be read: {}", error)
            })?
        };

        if let Some(exit_status) = status {
            return Ok(exit_status);
        }

        thread::sleep(Duration::from_millis(50));
    }
}

fn join_reader(
    reader: thread::JoinHandle<io::Result<Vec<u8>>>,
    stream_name: &str,
) -> Result<Vec<u8>, String> {
    reader
        .join()
        .map_err(|_| format!("The {} reader thread failed.", stream_name))?
        .map_err(|error| format!("The {} stream could not be read: {}", stream_name, error))
}

fn bounded_text(bytes: Vec<u8>, maximum_bytes: usize, stream_name: &str) -> Result<String, String> {
    if bytes.len() > maximum_bytes {
        return Err(format!(
            "The {} output exceeded the {} byte limit.",
            stream_name, maximum_bytes
        ));
    }

    Ok(String::from_utf8_lossy(&bytes).trim().to_string())
}

fn run_model_bridge_blocking(
    arguments: Vec<String>,
    timeout: Duration,
    cancellable: bool,
) -> Result<String, String> {
    let root = application_root()?;

    let mut command = Command::new(python_binary(&root));

    command
        .current_dir(&root)
        .env("PYTHONPATH", &root)
        .env("PYTHONUNBUFFERED", "1")
        .arg("-m")
        .arg(MODEL_BRIDGE_MODULE)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    for argument in arguments {
        command.arg(argument);
    }

    let mut child = command.spawn().map_err(|error| {
        format!(
            "The application model bridge could not be started: {}",
            error
        )
    })?;

    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "The worker stdout pipe is unavailable.".to_string())?;

    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "The worker stderr pipe is unavailable.".to_string())?;

    let stdout_reader = thread::spawn(move || read_pipe(stdout));

    let stderr_reader = thread::spawn(move || read_pipe(stderr));

    let shared_child = Arc::new(Mutex::new(child));

    if cancellable {
        store_active_child(Arc::clone(&shared_child))?;
    }

    let exit_result = wait_for_child(&shared_child, timeout);

    if cancellable {
        clear_active_child(&shared_child);
    }

    let maximum_output_bytes =
        read_environment_usize("MODEL_BRIDGE_MAX_OUTPUT_BYTES", DEFAULT_MAX_OUTPUT_BYTES);

    let stdout_bytes = join_reader(stdout_reader, "stdout")?;

    let stderr_bytes = join_reader(stderr_reader, "stderr")?;

    let standard_output = bounded_text(stdout_bytes, maximum_output_bytes, "stdout")?;

    let standard_error = bounded_text(stderr_bytes, maximum_output_bytes, "stderr")?;

    let exit_status = exit_result?;

    if !exit_status.success() {
        if CANCEL_REQUESTED.load(Ordering::SeqCst) {
            return Err("The request was cancelled.".to_string());
        }

        if !standard_output.is_empty() {
            return Err(standard_output);
        }

        if !standard_error.is_empty() {
            return Err(standard_error);
        }

        return Err(format!(
            "The worker exited unsuccessfully with status {}.",
            exit_status
        ));
    }

    if standard_output.is_empty() {
        return Err("The application model bridge returned an empty response.".to_string());
    }

    Ok(standard_output)
}

#[tauri::command]
pub async fn get_model_options() -> Result<String, String> {
    let timeout_seconds = read_environment_u64(
        "MODEL_OPTIONS_TIMEOUT_SECONDS",
        DEFAULT_OPTIONS_TIMEOUT_SECONDS,
    );

    tauri::async_runtime::spawn_blocking(move || {
        run_model_bridge_blocking(
            vec!["options".to_string()],
            Duration::from_secs(timeout_seconds),
            false,
        )
    })
    .await
    .map_err(|error| format!("The model-options worker task failed: {}", error))?
}

#[tauri::command]
pub async fn process_manual_model_request(
    question: String,
    option_id: String,
    capability: String,
    arguments_json: String,
) -> Result<String, String> {
    let guard = RequestGuard::acquire()?;

    let timeout_seconds = read_environment_u64(
        "MODEL_REQUEST_TIMEOUT_SECONDS",
        DEFAULT_REQUEST_TIMEOUT_SECONDS,
    );

    let result = tauri::async_runtime::spawn_blocking(move || {
        let _guard = guard;

        run_model_bridge_blocking(
            vec![
                "ask".to_string(),
                "--option-id".to_string(),
                option_id,
                "--question".to_string(),
                question,
                "--capability".to_string(),
                capability,
                "--arguments-json".to_string(),
                arguments_json,
            ],
            Duration::from_secs(timeout_seconds),
            true,
        )
    })
    .await
    .map_err(|error| format!("The model request worker task failed: {}", error))?;

    result
}

#[tauri::command]
pub fn cancel_manual_model_request() -> Result<String, String> {
    if !REQUEST_RUNNING.load(Ordering::SeqCst) {
        return Ok("No model request is currently running.".to_string());
    }

    CANCEL_REQUESTED.store(true, Ordering::SeqCst);

    let active = active_child()
        .lock()
        .map_err(|_| "The active worker lock is unavailable.".to_string())?
        .as_ref()
        .cloned();

    if let Some(child) = active {
        terminate_child(&child);
    }

    Ok("Cancellation was requested.".to_string())
}
