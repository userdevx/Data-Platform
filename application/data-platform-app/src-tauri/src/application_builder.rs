use serde::Serialize;
use std::fs;
use std::path::Path;
use std::path::PathBuf;

use crate::application_generation;

#[derive(Debug, Clone, Serialize)]
pub struct BuildPhase {
    pub id: String,
    pub label: String,
    pub status: String,
    pub detail: String,
}

#[derive(Debug, Serialize)]
struct ApplicationBuildPlan {
    version: String,
    request: String,
    application_type: String,
    frontend: String,
    backend: String,
    storage: String,
    build_checks: Vec<String>,
    test_checks: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct ApplicationBuildResult {
    pub success: bool,
    pub project_name: String,
    pub project_path: String,
    pub application_type: String,
    pub files: Vec<String>,
    pub message: String,

    pub phases: Vec<BuildPhase>,

    pub build_output: String,
    pub test_output: String,

    pub preview_path: Option<String>,
}

struct CommandResult {
    success: bool,
    output: String,
    command: String,
    exit_code: Option<i32>,
    timed_out: bool,
}

fn phase(id: &str, label: &str, status: &str, detail: &str) -> BuildPhase {
    BuildPhase {
        id: id.to_string(),
        label: label.to_string(),
        status: status.to_string(),
        detail: detail.to_string(),
    }
}

fn build_plan(request: &str, application_type: &str) -> Result<ApplicationBuildPlan, String> {
    match application_type {
        "Web application" => Ok(ApplicationBuildPlan {
            version: "dataworc.application-plan.v1".to_string(),

            request: request.to_string(),

            application_type: application_type.to_string(),

            frontend: "HTML/CSS/JavaScript".to_string(),

            backend: "Not required by starter build".to_string(),

            storage: "Not required by starter build".to_string(),

            build_checks: vec!["Validate generated HTML".to_string()],

            test_checks: vec!["Verify interactive application controls".to_string()],
        }),

        "Desktop application" => Ok(ApplicationBuildPlan {
            version: "dataworc.application-plan.v1".to_string(),

            request: request.to_string(),

            application_type: application_type.to_string(),

            frontend: "Python/Tkinter".to_string(),

            backend: "Local Python runtime".to_string(),

            storage: "Not required by starter build".to_string(),

            build_checks: vec!["Compile Python source".to_string()],

            test_checks: vec!["Import generated desktop module".to_string()],
        }),

        "Data application" => Ok(ApplicationBuildPlan {
            version: "dataworc.application-plan.v1".to_string(),

            request: request.to_string(),

            application_type: application_type.to_string(),

            frontend: "Command-line data interface".to_string(),

            backend: "Python data-processing runtime".to_string(),

            storage: "File-backed input".to_string(),

            build_checks: vec!["Compile Python source".to_string()],

            test_checks: vec!["Execute command help path".to_string()],
        }),

        "Automation tool" => Ok(ApplicationBuildPlan {
            version: "dataworc.application-plan.v1".to_string(),

            request: request.to_string(),

            application_type: application_type.to_string(),

            frontend: "Command-line automation interface".to_string(),

            backend: "Python automation runtime".to_string(),

            storage: "Not required by starter build".to_string(),

            build_checks: vec!["Compile Python source".to_string()],

            test_checks: vec!["Execute automation smoke test".to_string()],
        }),

        _ => Err(format!(
            "Unsupported application type: {}",
            application_type,
        )),
    }
}

fn write_json<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let serialized = serde_json::to_string_pretty(value)
        .map_err(|error| format!("Could not serialize {}: {}", path.display(), error,))?;

    fs::write(path, serialized)
        .map_err(|error| format!("Could not write {}: {}", path.display(), error,))
}

const COMMAND_TIMEOUT_SECONDS: u64 = 20;

fn execute_with_timeout(
    project_root: &Path,
    program: &str,
    arguments: &[&str],
    limit: std::time::Duration,
) -> Result<CommandResult, String> {
    let command = if arguments.is_empty() {
        program.to_string()
    } else {
        format!("{} {}", program, arguments.join(" "),)
    };

    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|error| format!("Could not create command output identifier: {}", error,))?
        .as_nanos();

    let identifier = format!("dataworc-{}-{}", std::process::id(), timestamp,);

    let stdout_path = std::env::temp_dir().join(format!("{}.stdout", identifier,));

    let stderr_path = std::env::temp_dir().join(format!("{}.stderr", identifier,));

    let stdout_file = std::fs::File::create(&stdout_path).map_err(|error| {
        format!(
            "Could not create temporary stdout file {}: {}",
            stdout_path.display(),
            error,
        )
    })?;

    let stderr_file = std::fs::File::create(&stderr_path).map_err(|error| {
        let _ = std::fs::remove_file(&stdout_path);

        format!(
            "Could not create temporary stderr file {}: {}",
            stderr_path.display(),
            error,
        )
    })?;

    let spawn_result = std::process::Command::new(program)
        .args(arguments)
        .current_dir(project_root)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::from(stdout_file))
        .stderr(std::process::Stdio::from(stderr_file))
        .spawn();

    let mut child = match spawn_result {
        Ok(child) => child,

        Err(error) => {
            let _ = std::fs::remove_file(&stdout_path);

            let _ = std::fs::remove_file(&stderr_path);

            return Err(format!("Could not start {}: {}", command, error,));
        }
    };

    let started = std::time::Instant::now();

    let mut timed_out = false;

    let status = loop {
        match child
            .try_wait()
            .map_err(|error| format!("Could not poll {}: {}", command, error,))?
        {
            Some(status) => {
                break status;
            }

            None => {
                if started.elapsed() >= limit {
                    timed_out = true;

                    let _ = child.kill();

                    let status = child.wait().map_err(|error| {
                        format!(
                            "Could not terminate timed-out command {}: {}",
                            command, error,
                        )
                    })?;

                    break status;
                }

                std::thread::sleep(std::time::Duration::from_millis(50));
            }
        }
    };

    let stdout = std::fs::read_to_string(&stdout_path).unwrap_or_default();

    let stderr = std::fs::read_to_string(&stderr_path).unwrap_or_default();

    let _ = std::fs::remove_file(&stdout_path);

    let _ = std::fs::remove_file(&stderr_path);

    let output = if stdout.is_empty() {
        stderr
    } else if stderr.is_empty() {
        stdout
    } else {
        format!("{}\n{}", stdout, stderr,)
    };

    let output = if timed_out {
        if output.trim().is_empty() {
            format!("Timed out after {} milliseconds.", limit.as_millis(),)
        } else {
            format!(
                "{}\nTimed out after {} milliseconds.",
                output,
                limit.as_millis(),
            )
        }
    } else {
        output
    };

    Ok(CommandResult {
        success: status.success() && !timed_out,

        output,

        command,

        exit_code: status.code(),

        timed_out,
    })
}

fn run_command(
    project_root: &Path,
    program: &str,
    arguments: &[&str],
) -> Result<CommandResult, String> {
    execute_with_timeout(
        project_root,
        program,
        arguments,
        std::time::Duration::from_secs(COMMAND_TIMEOUT_SECONDS),
    )
}

fn ensure_file(root: &Path, relative_path: &str) -> Result<(), String> {
    let path = root.join(relative_path);

    if !path.is_file() {
        return Err(format!(
            "Expected generated file does not exist: {}",
            path.display(),
        ));
    }

    let metadata = fs::metadata(&path)
        .map_err(|error| format!("Could not inspect {}: {}", path.display(), error,))?;

    if metadata.len() == 0 {
        return Err(format!("Generated file is empty: {}", path.display(),));
    }

    Ok(())
}

fn build_web_application(project_root: &Path) -> Result<CommandResult, String> {
    ensure_file(project_root, "index.html")?;

    run_command(
        project_root,
        "python3",
        &[
            "-c",
            r##"
from pathlib import Path
from html.parser import HTMLParser

path = Path("index.html")
text = path.read_text(encoding="utf-8")

required = [
    "<html",
    "</html>",
    "<body",
    "</body>",
]

missing = [
    item
    for item in required
    if item not in text.lower()
]

if missing:
    raise SystemExit(
        "Missing required HTML structure: "
        + ", ".join(missing)
    )

class Parser(HTMLParser):
    pass

parser = Parser()
parser.feed(text)
parser.close()

print("HTML validation passed.")
"##,
        ],
    )
}

fn test_web_application(project_root: &Path) -> Result<CommandResult, String> {
    run_command(
        project_root,
        "python3",
        &[
            "-c",
            r##"
from pathlib import Path

text = Path("index.html").read_text(
    encoding="utf-8"
)

required = [
    'id="primary-action"',
    'id="status"',
]

missing = [
    item
    for item in required
    if item not in text
]

if missing:
    raise SystemExit(
        "Interactive controls are missing: "
        + ", ".join(missing)
    )

print("Web smoke test passed.")
"##,
        ],
    )
}

fn build_python_application(project_root: &Path) -> Result<CommandResult, String> {
    ensure_file(project_root, "src/main.py")?;

    run_command(
        project_root,
        "python3",
        &["-m", "py_compile", "src/main.py"],
    )
}

fn test_desktop_application(project_root: &Path) -> Result<CommandResult, String> {
    run_command(
        project_root,
        "python3",
        &[
            "-c",
            r##"
import ast
from pathlib import Path


path = Path("src/main.py")

if not path.is_file():
    raise SystemExit(
        "Generated desktop source src/main.py does not exist."
    )


source = path.read_text(
    encoding="utf-8",
)


tree = ast.parse(
    source,
    filename=str(path),
)


application_classes = [
    node
    for node in ast.walk(tree)
    if (
        isinstance(node, ast.ClassDef)
        and node.name == "Application"
    )
]


if not application_classes:
    raise SystemExit(
        "Generated desktop source does not define Application."
    )


has_main_guard = False


for node in tree.body:
    if not isinstance(node, ast.If):
        continue

    test = node.test

    if not isinstance(test, ast.Compare):
        continue

    if not (
        isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
    ):
        continue

    if len(test.ops) != 1:
        continue

    if not isinstance(test.ops[0], ast.Eq):
        continue

    if len(test.comparators) != 1:
        continue

    comparator = test.comparators[0]

    if (
        isinstance(comparator, ast.Constant)
        and comparator.value == "__main__"
    ):
        has_main_guard = True
        break


if not has_main_guard:
    raise SystemExit(
        "Generated desktop source is missing a valid __main__ guard."
    )


print(
    "Desktop AST validation passed."
)
"##,
        ],
    )
}

fn test_data_application(project_root: &Path) -> Result<CommandResult, String> {
    run_command(project_root, "python3", &["src/main.py", "--help"])
}

fn test_automation_tool(project_root: &Path) -> Result<CommandResult, String> {
    run_command(
        project_root,
        "python3",
        &["src/main.py", "--input", "dataworc-smoke-test"],
    )
}

fn command_failure_category(execution: &CommandResult) -> &'static str {
    if execution.timed_out {
        return "timeout";
    }

    if execution.output.contains("SyntaxError") {
        return "syntax_error";
    }

    if execution.output.contains("ModuleNotFoundError") {
        return "missing_dependency";
    }

    "execution_failure"
}

fn command_failure_message(phase: &str, execution: &CommandResult) -> String {
    format!(
        "phase={}\ncategory={}\ncommand={}\nexit_code={:?}\ntimed_out={}\n\n{}",
        phase,
        command_failure_category(execution,),
        execution.command,
        execution.exit_code,
        execution.timed_out,
        execution.output,
    )
}

fn build_project(project_root: &Path, application_type: &str) -> Result<CommandResult, String> {
    match application_type {
        "Web application" => build_web_application(project_root),

        "Desktop application" | "Data application" | "Automation tool" => {
            build_python_application(project_root)
        }

        _ => Err(format!("No build strategy exists for {}", application_type,)),
    }
}

fn test_project(project_root: &Path, application_type: &str) -> Result<CommandResult, String> {
    match application_type {
        "Web application" => test_web_application(project_root),

        "Desktop application" => test_desktop_application(project_root),

        "Data application" => test_data_application(project_root),

        "Automation tool" => test_automation_tool(project_root),

        _ => Err(format!("No test strategy exists for {}", application_type,)),
    }
}

fn preview_path(project_root: &Path, application_type: &str) -> Option<String> {
    match application_type {
        "Web application" => Some(
            project_root
                .join("index.html")
                .to_string_lossy()
                .into_owned(),
        ),

        _ => None,
    }
}

#[tauri::command]
pub async fn start_application_build(
    request: String,
    application_type: String,
) -> Result<ApplicationBuildResult, String> {
    tauri::async_runtime::spawn_blocking(move || run_application_build(request, application_type))
        .await
        .map_err(|error| format!("Application build task failed: {}", error,))?
}

fn run_application_build(
    request: String,
    application_type: String,
) -> Result<ApplicationBuildResult, String> {
    let clean_request = request.trim();

    if clean_request.is_empty() {
        return Err("Describe the application before building.".to_string());
    }

    let mut phases = vec![phase(
        "planning",
        "Planning",
        "running",
        "Preparing the application build plan.",
    )];

    let plan = build_plan(clean_request, &application_type)?;

    phases[0] = phase("planning", "Planning", "success", "Build plan prepared.");

    phases.push(phase(
        "generation",
        "Generation",
        "running",
        "Generating the project workspace and source files.",
    ));

    let generated = application_generation::generate_application_scaffold(
        clean_request.to_string(),
        application_type.clone(),
    )?;

    let project_root = PathBuf::from(&generated.project_path);

    if !project_root.is_dir() {
        return Err(format!(
            "Generated project directory does not exist: {}",
            project_root.display(),
        ));
    }

    let plan_path = project_root.join("application-plan.json");

    write_json(&plan_path, &plan)?;

    phases[1] = phase(
        "generation",
        "Generation",
        "success",
        "Project workspace and source files generated.",
    );

    phases.push(phase(
        "build",
        "Build",
        "running",
        "Compiling and validating generated source.",
    ));

    let build = build_project(&project_root, &application_type)?;

    if !build.success {
        phases[2] = phase(
            "build",
            "Build",
            "error",
            "Generated source did not pass the build step.",
        );

        return Err(command_failure_message("build", &build));
    }

    phases[2] = phase(
        "build",
        "Build",
        "success",
        "Generated source passed the build step.",
    );

    phases.push(phase(
        "testing",
        "Testing",
        "running",
        "Running a real generated-project smoke test.",
    ));

    let test = test_project(&project_root, &application_type)?;

    if !test.success {
        phases[3] = phase(
            "testing",
            "Testing",
            "error",
            "Generated application failed its smoke test.",
        );

        return Err(command_failure_message("testing", &test));
    }

    phases[3] = phase(
        "testing",
        "Testing",
        "success",
        "Generated application passed its smoke test.",
    );

    phases.push(phase(
        "security",
        "Security",
        "pending",
        "Dedicated dependency and static-security scanning is the next builder stage.",
    ));

    phases.push(phase(
        "preview",
        "Preview",
        "success",
        if application_type == "Web application" {
            "Generated web application is ready to preview."
        } else {
            "Generated project is ready for the preview/runtime adapter."
        },
    ));

    let mut files = generated.files.clone();

    files.push("application-plan.json".to_string());

    files.push("build-report.json".to_string());

    let result = ApplicationBuildResult {
        success: true,

        project_name: generated.project_name,

        project_path: generated.project_path,

        application_type: generated.application_type,

        files,

        message: "Application generated, built, and tested successfully.".to_string(),

        phases: phases.clone(),

        build_output: build.output,

        test_output: test.output,

        preview_path: preview_path(&project_root, &application_type),
    };

    let report_path = project_root.join("build-report.json");

    write_json(&report_path, &result)?;

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_timeout_is_bounded() {
        let root = std::env::temp_dir();

        let started = std::time::Instant::now();

        let result = execute_with_timeout(
            &root,
            "python3",
            &["-c", "import time; time.sleep(5)"],
            std::time::Duration::from_millis(250),
        )
        .expect("timeout execution should return a structured result");

        assert!(!result.success,);

        assert!(result.timed_out,);

        assert_eq!(command_failure_category(&result,), "timeout",);

        assert!(
            started.elapsed() < std::time::Duration::from_secs(3,),
            "timeout executor did not terminate promptly",
        );
    }

    #[test]
    fn command_executor_captures_real_output() {
        let root = std::env::temp_dir();

        let result = execute_with_timeout(
            &root,
            "python3",
            &["-c", "print('dataworc-real-output')"],
            std::time::Duration::from_secs(2),
        )
        .expect("command should execute");

        assert!(result.success,);

        assert!(!result.timed_out,);

        assert!(result.output.contains("dataworc-real-output",),);
    }
}

#[cfg(test)]
mod desktop_validator_tests {
    use super::*;

    fn temporary_project(prefix: &str, source: &str) -> std::path::PathBuf {
        let identifier = format!(
            "{}-{}-{}",
            prefix,
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH,)
                .expect("system clock must be valid",)
                .as_nanos(),
        );

        let root = std::env::temp_dir().join(identifier);

        let src = root.join("src");

        std::fs::create_dir_all(&src).expect("temporary source directory should be created");

        std::fs::write(src.join("main.py"), source)
            .expect("temporary desktop source should be written");

        root
    }

    fn remove_project(root: std::path::PathBuf) {
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn desktop_validator_does_not_execute_generated_code() {
        let root = temporary_project(
            "desktop-no-execute",
            r#"
raise RuntimeError(
    "THIS CODE MUST NEVER EXECUTE"
)


class Application:
    pass


if __name__ == "__main__":
    Application()
"#,
        );

        let result =
            test_project(&root, "Desktop application").expect("Desktop validator should execute");

        assert!(
            result.success,
            "unexpected validation failure: {}",
            result.output,
        );

        assert!(
            result.output.contains("Desktop AST validation passed."),
            "unexpected validation output: {}",
            result.output,
        );

        assert!(
            !result.output.contains("THIS CODE MUST NEVER EXECUTE"),
            "generated source appears to have executed",
        );

        remove_project(root);
    }

    #[test]
    fn desktop_validator_requires_application_class() {
        let root = temporary_project(
            "desktop-missing-class",
            r#"
def main():
    pass


if __name__ == "__main__":
    main()
"#,
        );

        let result = test_project(&root, "Desktop application")
            .expect("Desktop validator should return a result");

        assert!(!result.success,);

        assert!(
            result.output.contains("does not define Application"),
            "unexpected validation output: {}",
            result.output,
        );

        remove_project(root);
    }

    #[test]
    fn desktop_validator_requires_main_guard() {
        let root = temporary_project(
            "desktop-missing-main-guard",
            r#"
class Application:
    pass
"#,
        );

        let result = test_project(&root, "Desktop application")
            .expect("Desktop validator should return a result");

        assert!(!result.success,);

        assert!(
            result.output.contains("missing a valid __main__ guard"),
            "unexpected validation output: {}",
            result.output,
        );

        remove_project(root);
    }

    #[test]
    fn desktop_validator_rejects_wrong_main_guard_operator() {
        let root = temporary_project(
            "desktop-wrong-main-guard",
            r#"
class Application:
    pass


if __name__ != "__main__":
    Application()
"#,
        );

        let result = test_project(&root, "Desktop application")
            .expect("Desktop validator should return a result");

        assert!(!result.success,);

        assert!(
            result.output.contains("missing a valid __main__ guard"),
            "unexpected validation output: {}",
            result.output,
        );

        remove_project(root);
    }

    #[test]
    fn desktop_validator_rejects_invalid_python() {
        let root = temporary_project(
            "desktop-invalid-python",
            r#"
class Application
    pass
"#,
        );

        let result = test_project(&root, "Desktop application")
            .expect("Desktop validator should return a result");

        assert!(!result.success,);

        assert!(
            result.output.contains("SyntaxError"),
            "unexpected validation output: {}",
            result.output,
        );

        remove_project(root);
    }
}
