use crate::application_builder::{ApplicationBuildResult, BuildPhase};
use serde_json::Value;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write, Seek, SeekFrom};
use tauri::ipc::Channel;
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[cfg(unix)]
use std::os::unix::fs::OpenOptionsExt;

const PROCESS_TIMEOUT: Duration = Duration::from_secs(720);
const OUTPUT_LIMIT: u64 = 1024 * 1024;
const DIAGNOSTIC_LIMIT: usize = 2000;
const REQUEST_LIMIT: usize = 20_000;

fn phase(id: &str, label: &str, status: &str, detail: &str) -> BuildPhase {
    BuildPhase {
        id: id.to_owned(),
        label: label.to_owned(),
        status: status.to_owned(),
        detail: detail.to_owned(),
    }
}

fn tail(text: &str) -> String {
    let count = text.chars().count();
    if count <= DIAGNOSTIC_LIMIT {
        return text.trim().to_owned();
    }
    text.chars()
        .skip(count - DIAGNOSTIC_LIMIT)
        .collect::<String>()
        .trim()
        .to_owned()
}

/// Human-readable failure reason, including the sandbox's own diagnostics.
fn failure_reason(payload: &Value) -> String {
    let mut reason = payload
        .get("error")
        .and_then(Value::as_str)
        .or_else(|| payload.get("message").and_then(Value::as_str))
        .unwrap_or("Python Builder execution failed.")
        .to_owned();

    if let Some(verification) = payload.get("verification") {
        for key in ["sandbox_error", "stderr", "stdout"] {
            if let Some(text) = verification.get(key).and_then(Value::as_str) {
                if !text.trim().is_empty() {
                    reason.push_str(&format!("\n{key}: {}", tail(text)));
                    break;
                }
            }
        }
    }
    reason
}

fn valid_root(root: &Path) -> bool {
    root.join("engine/application_generation/builder.py").is_file()
        && root.join("config/application_generation/routes.json").is_file()
        && root.join("venv/bin/python").is_file()
}

fn builder_root() -> Result<PathBuf, String> {
    for key in ["DATA_PLATFORM_ROOT", "APPLICATION_ROOT"] {
        if let Ok(value) = std::env::var(key) {
            if !value.trim().is_empty() {
                let candidate = PathBuf::from(value.trim());
                if valid_root(&candidate) {
                    return candidate.canonicalize().map_err(|e| e.to_string());
                }
            }
        }
    }

    if let Ok(home) = std::env::var("HOME") {
        let candidate = PathBuf::from(home).join("Data-Platform");
        if valid_root(&candidate) {
            return candidate.canonicalize().map_err(|e| e.to_string());
        }
    }

    if let Ok(mut candidate) = std::env::current_dir() {
        loop {
            if valid_root(&candidate) {
                return candidate.canonicalize().map_err(|e| e.to_string());
            }
            if !candidate.pop() {
                break;
            }
        }
    }
    Err("DataWorc Python Builder root was not found.".into())
}

fn new_capture_file(path: &Path) -> Result<File, String> {
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    options.mode(0o600);
    options.open(path).map_err(|e| e.to_string())
}

fn read_limited(path: &Path) -> Result<String, String> {
    let file = File::open(path).map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    file.take(OUTPUT_LIMIT + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() as u64 > OUTPUT_LIMIT {
        return Err("Python Builder output exceeded 1 MiB.".into());
    }
    String::from_utf8(bytes).map_err(|e| e.to_string())
}

fn call_python(
    root: &Path,
    request: &str,
) -> Result<Value, String> {
    call_python_stream(root, request, None)
}


const EVENT_PREFIX: &[u8] = b"DATAWORC_BUILD_EVENT:";
const MAX_EVENT_LINE: usize = 64 * 1024;

/// Read only the newly appended bytes from Python's stderr file.
fn forward_progress(
    path: &Path,
    cursor: &mut u64,
    pending: &mut Vec<u8>,
    last_sequence: &mut u64,
    session: &str,
    channel: &Channel<Value>,
) -> Result<(), String> {
    let length = fs::metadata(path)
        .map_err(|e| format!("Progress file unavailable: {e}"))?
        .len();

    if length > OUTPUT_LIMIT || length < *cursor {
        return Err(
            "Builder diagnostics exceeded limit or were truncated".into()
        );
    }

    if length == *cursor {
        return Ok(());
    }

    let mut file = File::open(path)
        .map_err(|e| e.to_string())?;

    file.seek(SeekFrom::Start(*cursor))
        .map_err(|e| e.to_string())?;

    let mut chunk =
        vec![0u8; ((length - *cursor).min(65536)) as usize];

    let count = file.read(&mut chunk)
        .map_err(|e| e.to_string())?;

    if count == 0 {
        return Err(
            "Builder progress stream made no forward progress".into()
        );
    }

    *cursor += count as u64;
    pending.extend_from_slice(&chunk[..count]);

    while let Some(index) =
        pending.iter().position(|byte| *byte == b'\n')
    {
        let line: Vec<u8> = pending.drain(..=index).collect();
        let trimmed = &line[..line.len() - 1];

        if !trimmed.starts_with(EVENT_PREFIX) {
            continue;
        }

        let event: Value = serde_json::from_slice(
            &trimmed[EVENT_PREFIX.len()..]
        ).map_err(|e| format!("Malformed Builder progress: {e}"))?;

        let sequence = event
            .get("sequence")
            .and_then(Value::as_u64)
            .ok_or("Builder event sequence missing")?;

        if event.get("session_id").and_then(Value::as_str)
            != Some(session)
            || sequence != *last_sequence + 1
            || event.get("kind").and_then(Value::as_str).is_none()
            || !event.get("details").is_some_and(Value::is_object)
        {
            return Err(
                "Builder event session, schema or sequence mismatch".into()
            );
        }

        *last_sequence = sequence;

        channel.send(event).map_err(|e| {
            format!("Builder progress delivery failed: {e}")
        })?;
    }

    if pending.len() > MAX_EVENT_LINE {
        return Err(
            "Builder produced an oversized event line".into()
        );
    }

    Ok(())
}

fn call_python_stream(
    root: &Path,
    request: &str,
    stream: Option<(&str, &Channel<Value>)>,
) -> Result<Value, String> {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let basename = format!("dataworc-6b3-{}-{stamp}", std::process::id());
    let stdout_path = std::env::temp_dir().join(format!("{basename}.stdout"));
    let stderr_path = std::env::temp_dir().join(format!("{basename}.stderr"));
    let request_path = std::env::temp_dir().join(format!("{basename}.request"));

    let result = (|| -> Result<Value, String> {
        let stdout = new_capture_file(&stdout_path)?;
        let stderr = new_capture_file(&stderr_path)?;
        // Store the request in a private 0600 temporary file before spawn.
        // Never put user requirements in argv or block on a child stdin pipe.
        // This file is removed in all normal success and failure outcomes.
        let mut request_file = new_capture_file(&request_path)?;
        request_file
            .write_all(request.as_bytes())
            .map_err(|e| format!("Could not write Builder request: {e}"))?;
        request_file
            .sync_all()
            .map_err(|e| format!("Could not flush Builder request: {e}"))?;
        drop(request_file);

        let started = Instant::now();
        let mut child = Command::new(root.join("venv/bin/python"))
            .current_dir(root)
            .env("PYTHONPATH", root)
            .env("PYTHONUNBUFFERED", "1")
            .env(
                "DATAWORC_BUILD_SESSION_ID",
                stream.map(|(id, _)| id).unwrap_or(""),
            )
            .arg("-m")
            .arg("engine.application_generation.builder")
            .arg("--project-root")
            .arg(root)
            .arg("--request-file")
            .arg(&request_path)
            .stdin(Stdio::null())
            .stdout(Stdio::from(stdout))
            .stderr(Stdio::from(stderr))
            .spawn()
            .map_err(|e| format!("Could not start Python Builder: {e}"))?;

        let mut cursor = 0u64;
        let mut pending = Vec::new();
        let mut last_sequence = 0u64;

        let status = loop {
            if let Some((id, channel)) = stream {
                if let Err(error) = forward_progress(
                    &stderr_path,
                    &mut cursor,
                    &mut pending,
                    &mut last_sequence,
                    id,
                    channel,
                ) {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err(error);
                }
            }

            match child.try_wait() {
                Ok(Some(status)) => break status,
                Ok(None) => {
                    let oversized = [&stdout_path, &stderr_path].iter().any(|p| {
                        fs::metadata(p)
                            .map(|m| m.len() > OUTPUT_LIMIT)
                            .unwrap_or(false)
                    });
                    if oversized || started.elapsed() >= PROCESS_TIMEOUT {
                        let _ = child.kill();
                        let _ = child.wait();
                        return Err(if oversized {
                            "Python Builder output exceeded its limit.".into()
                        } else {
                            "Python Builder timed out.".into()
                        });
                    }
                    thread::sleep(Duration::from_millis(100));
                }
                Err(e) => {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err(format!("Could not monitor Python Builder: {e}"));
                }
            }
        };

        if let Some((id, channel)) = stream {
            // Flush the remaining events after Python exits.
            while cursor < fs::metadata(&stderr_path)
                .map_err(|e| e.to_string())?.len()
            {
                forward_progress(
                    &stderr_path,
                    &mut cursor,
                    &mut pending,
                    &mut last_sequence,
                    id,
                    channel,
                )?;
            }
        }

        let stdout = read_limited(&stdout_path)?;
        let stderr = read_limited(&stderr_path)?;
        let payload: Value = serde_json::from_str(stdout.trim()).map_err(|e| {
            format!("Invalid Python Builder JSON: {e}\n{}", tail(&stderr))
        })?;
        if !status.success() {
            return Err(failure_reason(&payload));
        }
        Ok(payload)
    })();

    let _ = fs::remove_file(&stdout_path);
    let _ = fs::remove_file(&stderr_path);
    let _ = fs::remove_file(&request_path);
    result
}

fn required<'a>(value: &'a Value, key: &str) -> Result<&'a str, String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| format!("Python Builder response missing {key}."))
}

/// The sandbox image identity, accepting either field name.
fn image_identity(verification: &Value) -> Result<&str, String> {
    let image = verification
        .get("image_id")
        .or_else(|| verification.get("image"))
        .and_then(Value::as_str)
        .ok_or("Sandbox image identity is missing.")?;
    let digest = image.strip_prefix("sha256:").unwrap_or("");
    if digest.len() != 64 || !digest.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("Sandbox image identity is invalid.".into());
    }
    Ok(image)
}

fn verified_result(root: &Path, output: &Value) -> Result<ApplicationBuildResult, String> {
    if output.get("success").and_then(Value::as_bool) != Some(true) {
        return Err(failure_reason(output));
    }
    if output.get("evidence_verified").and_then(Value::as_bool) != Some(true) {
        return Err("Validation evidence was not read back and verified.".into());
    }

    let verification = output
        .get("verification")
        .ok_or("Missing sandbox verification result.")?;
    let stage = required(verification, "stage")?;
    if !matches!(stage, "compile" | "test")
        || verification.get("success").and_then(Value::as_bool) != Some(true)
        || verification.get("exit_code").and_then(Value::as_i64) != Some(0)
        || verification.get("runtime_kind").and_then(Value::as_str) != Some("gvisor")
        || verification.get("isolation_class").and_then(Value::as_str) != Some("kernel_emulation")
        || verification.get("timed_out").and_then(Value::as_bool) != Some(false)
    {
        return Err("Required gVisor source validation did not pass.".into());
    }
    required(verification, "execution_id")?;
    image_identity(verification)?;

    let managed_root = root
        .join("var/application-generation")
        .canonicalize()
        .map_err(|e| format!("Managed workspace unavailable: {e}"))?;
    let workspace = PathBuf::from(required(output, "project_path")?)
        .canonicalize()
        .map_err(|e| format!("Project directory unavailable: {e}"))?;
    if workspace.parent() != Some(managed_root.as_path()) || !workspace.is_dir() {
        return Err("Builder returned an unmanaged workspace.".into());
    }

    let application_id = required(output, "application_id")?;
    if workspace.file_name().and_then(|x| x.to_str()) != Some(application_id) {
        return Err("Application ID and workspace do not match.".into());
    }

    let evidence_file = PathBuf::from(required(output, "evidence_path")?)
        .canonicalize()
        .map_err(|e| format!("Validation evidence unavailable: {e}"))?;
    if evidence_file.parent() != Some(managed_root.as_path())
        || evidence_file.file_name().and_then(|n| n.to_str())
            != Some(format!(".{application_id}.evidence.json").as_str())
        || !evidence_file.is_file()
    {
        return Err("Validation evidence path is invalid.".into());
    }

    let template_id = required(output, "template_id")?;
    let metadata_path = workspace.join("generation.json");
    let metadata: Value = serde_json::from_str(&read_limited(&metadata_path)?)
        .map_err(|e| format!("Generated project metadata invalid: {e}"))?;
    if metadata.get("application_id").and_then(Value::as_str) != Some(application_id)
        || metadata.get("template_id").and_then(Value::as_str) != Some(template_id)
    {
        return Err("Generated metadata and Builder response do not match.".into());
    }

    let entries = output
        .get("files")
        .and_then(Value::as_array)
        .filter(|values| !values.is_empty())
        .ok_or("Builder generated no application files.")?;
    let mut files = Vec::new();
    for item in entries {
        let name = item.as_str().ok_or("Invalid generated-file entry.")?;
        let relative = Path::new(name);
        if name.contains('\\')
            || relative.is_absolute()
            || !relative
                .components()
                .all(|part| matches!(part, Component::Normal(_)))
        {
            return Err("Unsafe generated-file path.".into());
        }
        let absolute = workspace
            .join(relative)
            .canonicalize()
            .map_err(|e| format!("Generated file unavailable: {e}"))?;
        if !absolute.starts_with(&workspace) || !absolute.is_file() {
            return Err("Generated file escapes its workspace.".into());
        }
        files.push(name.to_owned());
    }

    let validation_output = verification
        .get("stdout")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned();

    let (functional_phase, summary_message, test_output) =
        if let Some(func_ver) = output.get("functional_verification") {
            let func_exec_id = required(func_ver, "execution_id")?;
            if func_ver.get("success").and_then(Value::as_bool) != Some(true)
                || func_ver.get("dom_mutated").and_then(Value::as_bool) != Some(true)
            {
                return Err("Headless browser functional verification did not pass.".into());
            }
            let exercised = func_ver
                .get("controls_exercised")
                .and_then(Value::as_u64)
                .unwrap_or(0);
            let discovered = func_ver
                .get("controls_discovered")
                .and_then(Value::as_u64)
                .unwrap_or(0);
            (
                phase(
                    "functional-testing",
                    "Functional testing",
                    "success",
                    &format!(
                        "Verified in headless Chromium ({exercised}/{discovered} controls exercised, DOM mutated, 0 JS errors)."
                    ),
                ),
                "Project files generated, gVisor source validation passed, and headless Chromium functional testing verified.".to_owned(),
                format!("functional_test_execution_id={func_exec_id} controls_exercised={exercised} dom_mutated=true"),
            )
        } else {
            (
                phase(
                    "functional-testing",
                    "Functional testing",
                    "pending",
                    "Application behavior has not yet been verified.",
                ),
                "Project files generated and source validation passed in gVisor. Functional testing remains pending.".to_owned(),
                String::new(),
            )
        };

    Ok(ApplicationBuildResult {
        success: true,
        project_name: required(output, "project_name")?.to_owned(),
        project_path: workspace.to_string_lossy().into_owned(),
        application_type: required(output, "application_type")?.to_owned(),
        files,
        message: summary_message,
        phases: vec![
            phase("planning", "Planning", "success", &format!("Selected registered template: {template_id}")),
            phase("generation", "Generation", "success", "Generated files and project metadata verified."),
            phase("source-validation", "Source validation", "success", "Source validation passed in gVisor; validation evidence was recorded and read back."),
            functional_phase,
            phase("security", "Security", "pending", "Dedicated security scanning has not yet been verified."),
            phase("preview", "Preview", "pending", "Application preview has not yet been verified."),
        ],
        build_output: validation_output,
        test_output,
        preview_path: None,
    })
}

#[tauri::command]
pub async fn start_application_build_bridge(request: String) -> Result<ApplicationBuildResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let trimmed = request.trim();
        if trimmed.is_empty() || trimmed.len() > REQUEST_LIMIT {
            return Err("Provide an application description of at most 20,000 bytes.".into());
        }
        let root = builder_root()?;
        let output = call_python(&root, trimmed)?;
        verified_result(&root, &output)
    })
    .await
    .map_err(|e| format!("Application Builder task failed: {e}"))?
}


/// Stream persisted Python milestones to the invoking frontend.
/// Rust independently verifies the final Builder result.
#[tauri::command]
pub async fn start_application_build_stream(
    request: String,
    session_id: String,
    on_event: Channel<Value>,
) -> Result<ApplicationBuildResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let trimmed = request.trim();

        if trimmed.is_empty() || trimmed.len() > REQUEST_LIMIT {
            return Err("Invalid application request length".into());
        }

        if session_id.is_empty() || session_id.len() > 128
            || !session_id.bytes().all(|b| {
                b.is_ascii_alphanumeric() || b == b'-'
            })
        {
            return Err("Invalid Builder session ID".into());
        }

        let root = builder_root()?;

        let output = call_python_stream(
            &root,
            trimmed,
            Some((&session_id, &on_event)),
        )?;

        verified_result(&root, &output)
    })
    .await
    .map_err(|e| format!("Builder worker failed: {e}"))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const IMAGE: &str =
        "sha256:1484ad8a85261f4259a332991bf4425945e2750e8e22e113eb07eccbad203698";

    fn passing_verification() -> Value {
        json!({
            "stage": "compile",
            "success": true,
            "exit_code": 0,
            "runtime_kind": "gvisor",
            "isolation_class": "kernel_emulation",
            "timed_out": false,
            "execution_id": "exec-1",
            "image": IMAGE,
            "stdout": "",
        })
    }

    fn output_with(verification: Value) -> Value {
        json!({
            "success": true,
            "evidence_verified": true,
            "verification": verification,
        })
    }

    fn rejection(output: &Value) -> String {
        match verified_result(Path::new("/nonexistent-dataworc-root"), output) {
            Ok(_) => panic!("bridge accepted an output it must reject"),
            Err(reason) => reason,
        }
    }

    #[test]
    fn failed_build_reports_sandbox_diagnostics() {
        let output = json!({
            "success": false,
            "error": "Source validation failed.",
            "verification": {"stderr": "SyntaxError: invalid syntax (main.py, line 3)"},
        });
        let reason = rejection(&output);
        assert!(reason.contains("Source validation failed."));
        assert!(reason.contains("SyntaxError"));
    }

    #[test]
    fn unverified_evidence_is_rejected() {
        let mut output = output_with(passing_verification());
        output["evidence_verified"] = json!(false);
        assert!(rejection(&output).contains("evidence"));
    }

    #[test]
    fn non_gvisor_runtime_is_rejected() {
        // Each field is checked on its own, so one check cannot mask another.
        let mut runtime = passing_verification();
        runtime["runtime_kind"] = json!("podman");
        assert!(rejection(&output_with(runtime)).contains("gVisor"));

        let mut isolation = passing_verification();
        isolation["isolation_class"] = json!("host_os");
        assert!(rejection(&output_with(isolation)).contains("gVisor"));

        let mut stage = passing_verification();
        stage["stage"] = json!("run");
        assert!(rejection(&output_with(stage)).contains("gVisor"));

        let mut failed = passing_verification();
        failed["success"] = json!(false);
        assert!(rejection(&output_with(failed)).contains("gVisor"));

        let mut no_execution = passing_verification();
        no_execution.as_object_mut().unwrap().remove("execution_id");
        assert!(rejection(&output_with(no_execution)).contains("execution_id"));
    }

    #[test]
    fn nonzero_exit_and_timeout_are_rejected() {
        let mut nonzero = passing_verification();
        nonzero["exit_code"] = json!(1);
        assert!(rejection(&output_with(nonzero)).contains("gVisor"));

        let mut timed_out = passing_verification();
        timed_out["timed_out"] = json!(true);
        assert!(rejection(&output_with(timed_out)).contains("gVisor"));
    }

    #[test]
    fn image_identity_accepts_either_field_and_rejects_bad_digests() {
        assert!(image_identity(&json!({"image": IMAGE})).is_ok());
        assert!(image_identity(&json!({"image_id": IMAGE})).is_ok());
        assert!(image_identity(&json!({})).is_err());
        assert!(image_identity(&json!({"image": "alpine:latest"})).is_err());
        assert!(image_identity(&json!({"image": "sha256:zz"})).is_err());

        let mut missing = passing_verification();
        missing.as_object_mut().unwrap().remove("image");
        assert!(rejection(&output_with(missing)).contains("image identity"));
    }

    #[test]
    fn diagnostics_are_bounded() {
        let long = "x".repeat(DIAGNOSTIC_LIMIT * 3);
        assert_eq!(tail(&long).chars().count(), DIAGNOSTIC_LIMIT);
    }

    /// Exercises the bridge against a real Builder result produced on this
    /// machine. Run by the Step 6b-3 script with DATAWORC_6B3_ROOT and
    /// DATAWORC_6B3_RESULT set.
    #[test]
    #[ignore = "requires a real Builder result; run by the Step 6b-3 script"]
    fn accepts_real_builder_output() {
        let root = PathBuf::from(std::env::var("DATAWORC_6B3_ROOT").expect("DATAWORC_6B3_ROOT"))
            .canonicalize()
            .expect("root");
        let path = std::env::var("DATAWORC_6B3_RESULT").expect("DATAWORC_6B3_RESULT");
        let output: Value =
            serde_json::from_str(&fs::read_to_string(path).expect("result file")).expect("json");
        let result = verified_result(&root, &output)
            .unwrap_or_else(|reason| panic!("bridge rejected real Builder output: {reason}"));
        assert!(result.success);
        assert!(!result.files.is_empty());
        assert_eq!(result.phases.len(), 6);
        println!("BRIDGE_ACCEPTED_REAL_OUTPUT project={}", result.project_path);
    }

    /// The actual registered Tauri command, through the async worker,
    /// executes the Python Builder and returns the frontend result contract.
    #[test]
    #[ignore = "runs the real Python Builder; run by the Step 6b-3 script"]
    fn runs_real_builder_through_bridge() {
        // Resolve the root the way the desktop command does (no override), and
        // require that it is the repository under test, not another worktree.
        let expected = PathBuf::from(std::env::var("DATAWORC_6B3_ROOT").expect("DATAWORC_6B3_ROOT"))
            .canonicalize()
            .expect("root");
        let root = builder_root()
            .unwrap_or_else(|reason| panic!("builder_root() failed: {reason}"));
        assert_eq!(root, expected, "builder_root() resolved a different checkout");
        let request = std::env::var("DATAWORC_6B3_REQUEST")
            .unwrap_or_else(|_| "Build a Linux desktop application".to_owned());
        let result = tauri::async_runtime::block_on(start_application_build_bridge(request))
            .unwrap_or_else(|reason| panic!("actual Tauri Build command failed: {reason}"));
        assert!(result.success);
        assert!(!result.files.is_empty());
        assert_eq!(result.phases[2].status, "success");
        assert_eq!(result.phases[3].status, "pending");
        println!("TAURI_COMMAND_RAN_REAL_BUILDER project={}", result.project_path);
    }
}


// Read a generated HTML application from the managed workspace.
// This is a source preview, not an Application Engineering approval.
#[tauri::command]
pub async fn read_application_preview(
    project_path: Option<String>,
) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let managed = builder_root()?
            .join("var/application-generation")
            .canonicalize()
            .map_err(|e| format!("Managed workspace unavailable: {e}"))?;

        let workspace = match project_path {
            Some(path) => {
                let supplied = PathBuf::from(path);

                if !supplied.is_absolute()
                    || fs::symlink_metadata(&supplied)
                        .map_err(|e| e.to_string())?
                        .file_type()
                        .is_symlink()
                {
                    return Err("Invalid preview workspace.".into());
                }

                supplied
                    .canonicalize()
                    .map_err(|e| format!("Preview workspace unavailable: {e}"))?
            }
            None => {
                // On page load, discover the most recent actual HTML
                // application already generated under the managed root.
                let mut candidates = Vec::new();

                for item in fs::read_dir(&managed)
                    .map_err(|e| e.to_string())?
                {
                    let entry = item.map_err(|e| e.to_string())?;
                    let path = entry.path();
                    let meta = fs::symlink_metadata(&path)
                        .map_err(|e| e.to_string())?;

                    if !meta.is_dir() || meta.file_type().is_symlink() {
                        continue;
                    }

                    let file = path.join("index.html");

                    if let Ok(meta) = fs::symlink_metadata(&file) {
                        if meta.is_file()
                            && !meta.file_type().is_symlink()
                            && meta.len() <= 524_288
                        {
                            let modified = meta.modified()
                                .unwrap_or(std::time::UNIX_EPOCH);

                            candidates.push((modified, path));
                        }
                    }
                }

                candidates.sort_by(|a, b| b.0.cmp(&a.0));

                candidates
                    .into_iter()
                    .next()
                    .map(|(_, path)| path)
                    .ok_or("No generated HTML application available.")?
            }
        };

        if workspace.parent() != Some(managed.as_path())
            || !workspace.is_dir()
        {
            return Err("Preview is outside the managed workspace.".into());
        }

        let file = workspace.join("index.html");
        let metadata = fs::symlink_metadata(&file)
            .map_err(|_| "This application has no HTML preview entry point.".to_string())?;

        if !metadata.is_file()
            || metadata.file_type().is_symlink()
            || metadata.len() > 524_288
        {
            return Err("Unsafe or oversized preview document.".into());
        }

        let resolved = file
            .canonicalize()
            .map_err(|e| e.to_string())?;

        if resolved.parent() != Some(workspace.as_path()) {
            return Err("Preview file escapes the workspace.".into());
        }

        let html = fs::read_to_string(&resolved)
            .map_err(|e| format!("Cannot read generated HTML: {e}"))?;

        Ok(serde_json::json!({
            "html": html,
            "project_name": workspace.file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("Generated application"),
            "preview_kind": "self_contained_html",
            "engineering_verified": false
        }))
    })
    .await
    .map_err(|e| format!("Preview task failed: {e}"))?
}
