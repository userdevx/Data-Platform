use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct BuildPhase {
    pub id: String,
    pub label: String,
    pub status: String,
    pub detail: String,
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
