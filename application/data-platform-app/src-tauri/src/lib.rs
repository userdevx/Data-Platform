use serde::Serialize;
use serde_json::json;
use std::collections::{HashMap, HashSet};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

const DATA_ENGINE_MAX_BYTES: u64 = 500 * 1024 * 1024;

#[derive(Serialize)]
struct UserLocation {
    id: String,
    label: String,
    path: String,
}

#[derive(Serialize)]
struct DirectoryEntry {
    name: String,
    path: String,
    entry_type: String,
    size: Option<u64>,
}

#[derive(Serialize)]
struct ConnectionResult {
    success: bool,
    message: String,
    source_type: String,
    path: Option<String>,
    storage_path: Option<String>,
}

#[derive(Serialize)]
struct CreateDatabaseResult {
    success: bool,
    message: String,
    database_name: String,
    database_path: String,
    source_file: String,
}

#[derive(Serialize)]
struct WorkspaceDashboard {
    connected_sources: usize,
    raw_records: usize,
    databases: usize,
    data_quality: String,
    storage_used: String,
    active_database: String,
    recent_ingestion_source: String,
    recent_ingestion_status: String,
    pipeline_raw_to_bronze: String,
    pipeline_bronze_to_silver: String,
    pipeline_silver_to_gold: String,
}

#[derive(Serialize)]
struct WorkspaceOutput {
    title: String,
    message: String,
    rows: Vec<HashMap<String, String>>,
}

fn project_root() -> Result<PathBuf, String> {
    let current = std::env::current_dir()
        .map_err(|error| format!("Unable to read current directory: {}", error))?;

    if current.ends_with("src-tauri") {
        return current
            .parent()
            .map(|path| path.to_path_buf())
            .ok_or("Unable to locate project root.".to_string());
    }

    Ok(current)
}

fn data_dir() -> Result<PathBuf, String> {
    let path = project_root()?.join("data");

    for folder in [
        "",
        "imports",
        "databases",
        "exports",
        "data_lake/raw",
        "data_lake/bronze",
        "data_lake/silver",
        "data_lake/gold",
    ] {
        fs::create_dir_all(path.join(folder))
            .map_err(|error| format!("Unable to create Data Drive folder: {}", error))?;
    }

    Ok(path)
}

fn sources_path() -> Result<PathBuf, String> {
    Ok(data_dir()?.join("sources.jsonl"))
}

fn records_path() -> Result<PathBuf, String> {
    Ok(data_dir()?.join("records.jsonl"))
}

fn layer_path(layer: &str) -> Result<PathBuf, String> {
    Ok(data_dir()?.join("data_lake").join(layer).join("records.jsonl"))
}

fn logs_dir() -> Result<PathBuf, String> {
    let path = project_root()?.join("logs");
    fs::create_dir_all(&path).map_err(|error| format!("Unable to create logs folder: {}", error))?;
    Ok(path)
}

fn timestamp() -> Result<u64, String> {
    Ok(SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| format!("Unable to get timestamp: {}", error))?
        .as_secs())
}

fn path_to_string(path: Option<PathBuf>) -> Option<String> {
    path.map(|value| value.to_string_lossy().to_string())
}

fn size_of(path: &Path) -> u64 {
    if !path.exists() {
        return 0;
    }

    if path.is_file() {
        return path.metadata().map(|m| m.len()).unwrap_or(0);
    }

    let mut total = 0;

    if let Ok(entries) = fs::read_dir(path) {
        for entry in entries.flatten() {
            total += size_of(&entry.path());
        }
    }

    total
}

fn format_bytes(size: u64) -> String {
    if size < 1024 {
        return format!("{} B", size);
    }

    if size < 1024 * 1024 {
        return format!("{} KB", size / 1024);
    }

    if size < 1024 * 1024 * 1024 {
        return format!("{:.1} MB", size as f64 / 1024.0 / 1024.0);
    }

    format!("{:.2} GB", size as f64 / 1024.0 / 1024.0 / 1024.0)
}

fn read_lines(path: &Path) -> Vec<String> {
    if !path.exists() {
        return Vec::new();
    }

    fs::read_to_string(path)
        .unwrap_or_default()
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| line.to_string())
        .collect()
}

fn line_count(path: &Path) -> usize {
    read_lines(path).len()
}

fn append_jsonl(path: &Path, value: serde_json::Value) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| format!("Unable to create parent folder: {}", error))?;
    }

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| format!("Unable to open JSONL file: {}", error))?;

    writeln!(file, "{}", value).map_err(|error| format!("Unable to write JSONL record: {}", error))?;

    Ok(())
}

fn log_event(message: &str) -> Result<(), String> {
    let path = logs_dir()?.join("engine.log");
    let now = timestamp()?;

    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| format!("Unable to open engine log: {}", error))?;

    writeln!(file, "{} {}", now, message).map_err(|error| format!("Unable to write engine log: {}", error))?;

    Ok(())
}

fn row(values: Vec<(&str, String)>) -> HashMap<String, String> {
    let mut output = HashMap::new();

    for (key, value) in values {
        output.insert(key.to_string(), value);
    }

    output
}

fn unique_path(folder: &Path, file_name: &str) -> PathBuf {
    let mut target = folder.join(file_name);

    if !target.exists() {
        return target;
    }

    let path = Path::new(file_name);
    let stem = path.file_stem().unwrap_or_default().to_string_lossy();
    let extension = path.extension().map(|ext| ext.to_string_lossy().to_string());

    let mut counter = 1;

    loop {
        let new_name = match &extension {
            Some(ext) => format!("{}_{}.{}", stem, counter, ext),
            None => format!("{}_{}", stem, counter),
        };

        target = folder.join(new_name);

        if !target.exists() {
            return target;
        }

        counter += 1;
    }
}

fn safe_name(name: &str) -> String {
    name.to_lowercase()
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect::<String>()
        .trim_matches('_')
        .to_string()
}

fn connected_sources_count() -> Result<usize, String> {
    let mut unique = HashSet::new();

    for line in read_lines(&sources_path()?) {
        if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
            let stored_path = value["metadata"]["stored_path"].as_str().unwrap_or("");
            if !stored_path.is_empty() {
                unique.insert(stored_path.to_string());
            }
        }
    }

    Ok(unique.len())
}

fn data_quality() -> Result<String, String> {
    let raw = layer_path("raw")?;
    let lines = read_lines(&raw);

    if lines.is_empty() {
        return Ok("0% No Data".to_string());
    }

    let mut valid = 0usize;

    for line in &lines {
        if let Ok(value) = serde_json::from_str::<serde_json::Value>(line) {
            let required = ["source", "category", "sensor_type", "value", "unit", "timestamp"];

            if required.iter().all(|key| value.get(*key).is_some() && !value[*key].is_null()) {
                valid += 1;
            }
        }
    }

    let percent = ((valid as f64 / lines.len() as f64) * 100.0).round() as usize;

    let label = if percent >= 90 {
        "Good"
    } else if percent >= 70 {
        "Fair"
    } else {
        "Poor"
    };

    Ok(format!("{}% {}", percent, label))
}

fn pipeline_status() -> Result<(String, String, String), String> {
    let raw = line_count(&layer_path("raw")?);
    let bronze = line_count(&layer_path("bronze")?);
    let silver = line_count(&layer_path("silver")?);
    let gold = line_count(&layer_path("gold")?);

    let raw_to_bronze = if bronze > 0 {
        "Success"
    } else if raw > 0 {
        "Ready"
    } else {
        "Waiting"
    };

    let bronze_to_silver = if silver > 0 {
        "Success"
    } else if bronze > 0 {
        "Ready"
    } else {
        "Waiting"
    };

    let silver_to_gold = if gold > 0 {
        "Success"
    } else if silver > 0 {
        "Ready"
    } else {
        "Waiting"
    };

    Ok((
        raw_to_bronze.to_string(),
        bronze_to_silver.to_string(),
        silver_to_gold.to_string(),
    ))
}

fn recent_ingestion() -> Result<(String, String), String> {
    let raw = layer_path("raw")?;
    let lines = read_lines(&raw);

    if lines.is_empty() {
        return Ok(("None".to_string(), "Waiting".to_string()));
    }

    let last = lines.last().cloned().unwrap_or_default();

    if let Ok(value) = serde_json::from_str::<serde_json::Value>(&last) {
        let file_name = value["metadata"]["file_name"]
            .as_str()
            .unwrap_or("file_source")
            .to_string();

        return Ok((file_name, "Success".to_string()));
    }

    Ok(("file_source".to_string(), "Success".to_string()))
}

fn log_rows() -> Result<Vec<HashMap<String, String>>, String> {
    let paths = vec![
        ("engine.log", logs_dir()?.join("engine.log")),
        ("errors.log", logs_dir()?.join("errors.log")),
    ];

    let mut output = Vec::new();
    let mut id = 1usize;

    for (name, path) in paths {
        let lines = read_lines(&path);

        if lines.is_empty() {
            output.push(row(vec![
                ("log_id", id.to_string()),
                ("log_file", name.to_string()),
                ("timestamp", "—".to_string()),
                ("level", "INFO".to_string()),
                ("action", "log_check".to_string()),
                ("message", "No log records found.".to_string()),
                ("source", "data_engine".to_string()),
            ]));

            id += 1;
            continue;
        }

        for line in lines {
            let level = if line.contains("[ERROR]") {
                "ERROR"
            } else if line.contains("[WARN]") {
                "WARN"
            } else {
                "INFO"
            };

            let action = if line.contains("Data connected") {
                "connect_data"
            } else if line.contains("Database created") {
                "create_database"
            } else if line.contains("Pipeline completed") {
                "run_pipeline"
            } else if line.contains("Query executed") {
                "run_query"
            } else if line.contains("Export completed") {
                "export"
            } else if line.contains("Dashboard refreshed") {
                "refresh"
            } else {
                "system_event"
            };

            let mut parts = line.splitn(2, ' ');
            let time = parts.next().unwrap_or("—").to_string();
            let message = parts.next().unwrap_or("").to_string();

            output.push(row(vec![
                ("log_id", id.to_string()),
                ("log_file", name.to_string()),
                ("timestamp", time),
                ("level", level.to_string()),
                ("action", action.to_string()),
                ("message", message),
                ("source", "data_engine".to_string()),
            ]));

            id += 1;
        }
    }

    Ok(output)
}

fn csv_escape(value: &str) -> String {
    let escaped = value.replace('"', "\"\"");
    if escaped.contains(',') || escaped.contains('"') || escaped.contains('\n') {
        format!("\"{}\"", escaped)
    } else {
        escaped
    }
}

#[tauri::command]
fn get_user_locations() -> Vec<UserLocation> {
    let mut locations = Vec::new();

    if let Some(path) = path_to_string(dirs::home_dir()) {
        locations.push(UserLocation { id: "home".to_string(), label: "Home".to_string(), path });
    }

    if let Some(path) = path_to_string(dirs::document_dir()) {
        locations.push(UserLocation { id: "documents".to_string(), label: "Documents".to_string(), path });
    }

    if let Some(path) = path_to_string(dirs::download_dir()) {
        locations.push(UserLocation { id: "downloads".to_string(), label: "Downloads".to_string(), path });
    }

    if let Some(path) = path_to_string(dirs::picture_dir()) {
        locations.push(UserLocation { id: "pictures".to_string(), label: "Pictures".to_string(), path });
    }

    if let Some(path) = path_to_string(dirs::video_dir()) {
        locations.push(UserLocation { id: "videos".to_string(), label: "Videos".to_string(), path });
    }

    if let Ok(path) = data_dir() {
        locations.push(UserLocation {
            id: "data-drive".to_string(),
            label: "Data Drive".to_string(),
            path: path.to_string_lossy().to_string(),
        });
    }

    locations
}

#[tauri::command]
fn read_directory(path: String) -> Result<Vec<DirectoryEntry>, String> {
    let directory = Path::new(&path);

    if !directory.exists() {
        return Err("Directory does not exist.".to_string());
    }

    if !directory.is_dir() {
        return Err("Selected path is not a directory.".to_string());
    }

    let mut entries = Vec::new();

    for entry in fs::read_dir(directory)
        .map_err(|error| format!("Unable to read directory: {}", error))?
        .flatten()
    {
        let metadata = match entry.metadata() {
            Ok(value) => value,
            Err(_) => continue,
        };

        entries.push(DirectoryEntry {
            name: entry.file_name().to_string_lossy().to_string(),
            path: entry.path().to_string_lossy().to_string(),
            entry_type: if metadata.is_dir() { "Folder".to_string() } else { "File".to_string() },
            size: if metadata.is_file() { Some(metadata.len()) } else { None },
        });
    }

    entries.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));

    Ok(entries)
}

#[tauri::command]
fn connect_data(source_type: String, path: Option<String>) -> Result<ConnectionResult, String> {
    let selected_path = path.clone().ok_or("Choose a path before connecting data.")?;
    let selected_file = Path::new(&selected_path);

    if !selected_file.exists() {
        return Err("Selected path does not exist.".to_string());
    }

    if !selected_file.is_file() {
        return Err("Select a file before connecting data.".to_string());
    }

    let metadata = fs::metadata(selected_file)
        .map_err(|error| format!("Unable to read file metadata: {}", error))?;

    let data = data_dir()?;
    let current_size = size_of(&data);

    if current_size + metadata.len() > DATA_ENGINE_MAX_BYTES {
        return Err("Data Drive storage limit reached.".to_string());
    }

    let imports = data.join("imports");
    let file_name = selected_file
        .file_name()
        .ok_or("Unable to read file name.".to_string())?
        .to_string_lossy()
        .to_string();

    let stored_file = unique_path(&imports, &file_name);

    fs::copy(selected_file, &stored_file)
        .map_err(|error| format!("Unable to copy file into Data Drive: {}", error))?;

    let now = timestamp()?;
    let stored_path = stored_file.to_string_lossy().to_string();
    let source_id = format!("source_{}", now);

    let source_record = json!({
        "source": "data_platform_ui",
        "category": "connected_source",
        "sensor_type": "file_source",
        "value": stored_path,
        "unit": "file_path",
        "timestamp": now,
        "metadata": {
            "source_id": source_id,
            "source_type": source_type,
            "file_name": file_name,
            "original_path": selected_path,
            "stored_path": stored_path,
            "status": "connected"
        }
    });

    append_jsonl(&sources_path()?, source_record.clone())?;

    let event_record = json!({
        "source": "data_platform_ui",
        "category": "data_connection",
        "sensor_type": "file_source",
        "value": stored_path,
        "unit": "file_path",
        "timestamp": now,
        "metadata": {
            "action": "connect_data",
            "source_id": source_id,
            "stored_path": stored_path,
            "status": "connected"
        }
    });

    append_jsonl(&records_path()?, event_record)?;

    let raw_record = json!({
        "source": "data_platform_ui",
        "category": "raw",
        "sensor_type": "file_source",
        "value": stored_path,
        "unit": "file_path",
        "timestamp": now,
        "metadata": {
            "action": "connect_data",
            "source_id": source_id,
            "file_name": file_name,
            "stage": "raw",
            "file_size_bytes": metadata.len(),
            "status": "ready_for_pipeline"
        }
    });

    append_jsonl(&layer_path("raw")?, raw_record)?;

    log_event("[INFO] Data connected and stored in Data Engine.")?;

    Ok(ConnectionResult {
        success: true,
        message: "Data connected and stored in Data Engine.".to_string(),
        source_type,
        path,
        storage_path: Some(stored_path),
    })
}

#[tauri::command]
fn create_database(
    database_name: String,
    selected_file_path: String,
    storage_type: String,
) -> Result<CreateDatabaseResult, String> {
    let clean_name = safe_name(&database_name);

    if clean_name.is_empty() {
        return Err("Database name is required.".to_string());
    }

    let selected_file = Path::new(&selected_file_path);

    if !selected_file.exists() || !selected_file.is_file() {
        return Err("Selected file does not exist or is not a file.".to_string());
    }

    let database_folder = data_dir()?.join("databases").join(&clean_name);
    let files_folder = database_folder.join("files");

    fs::create_dir_all(&files_folder)
        .map_err(|error| format!("Unable to create database folder: {}", error))?;

    let file_name = selected_file
        .file_name()
        .ok_or("Unable to read selected file name.".to_string())?
        .to_string_lossy()
        .to_string();

    let stored_file = unique_path(&files_folder, &file_name);

    fs::copy(selected_file, &stored_file)
        .map_err(|error| format!("Unable to copy file into database: {}", error))?;

    let now = timestamp()?;

    let database_metadata = json!({
        "database_name": clean_name,
        "storage_type": storage_type,
        "source_file": selected_file_path,
        "stored_file": stored_file.to_string_lossy().to_string(),
        "created_at": now,
        "status": "created"
    });

    fs::write(
        database_folder.join("database.json"),
        serde_json::to_string_pretty(&database_metadata)
            .map_err(|error| format!("Unable to serialize database metadata: {}", error))?,
    )
    .map_err(|error| format!("Unable to write database metadata: {}", error))?;

    let record = json!({
        "source": "data_platform_ui",
        "category": "database",
        "sensor_type": "create_database",
        "value": clean_name,
        "unit": "database",
        "timestamp": now,
        "metadata": database_metadata
    });

    fs::write(database_folder.join("records.jsonl"), format!("{}\n", record))
        .map_err(|error| format!("Unable to write database record: {}", error))?;

    append_jsonl(&records_path()?, record)?;

    log_event("[INFO] Database created.")?;

    Ok(CreateDatabaseResult {
        success: true,
        message: "Database created.".to_string(),
        database_name: clean_name,
        database_path: database_folder.to_string_lossy().to_string(),
        source_file: selected_file_path,
    })
}

#[tauri::command]
fn workspace_refresh(database_name: String, database_path: String) -> Result<WorkspaceDashboard, String> {
    let data = data_dir()?;
    let raw = line_count(&layer_path("raw")?);
    let databases = fs::read_dir(data.join("databases"))
        .map_err(|error| format!("Unable to read databases folder: {}", error))?
        .flatten()
        .filter(|entry| entry.path().is_dir())
        .count();

    let (recent_source, recent_status) = recent_ingestion()?;
    let (raw_to_bronze, bronze_to_silver, silver_to_gold) = pipeline_status()?;

    log_event("[INFO] Dashboard refreshed.")?;

    Ok(WorkspaceDashboard {
        connected_sources: connected_sources_count()?,
        raw_records: raw,
        databases,
        data_quality: data_quality()?,
        storage_used: format_bytes(size_of(&data)),
        active_database: if database_name.is_empty() { database_path } else { database_name },
        recent_ingestion_source: recent_source,
        recent_ingestion_status: recent_status,
        pipeline_raw_to_bronze: raw_to_bronze,
        pipeline_bronze_to_silver: bronze_to_silver,
        pipeline_silver_to_gold: silver_to_gold,
    })
}

#[tauri::command]
fn workspace_action(
    action: String,
    database_name: String,
    database_path: String,
) -> Result<WorkspaceOutput, String> {
    match action.as_str() {
        "Dashboard" => Ok(WorkspaceOutput {
            title: "Dashboard".to_string(),
            message: "Dashboard loaded from Data Engine state.".to_string(),
            rows: vec![row(vec![
                ("section", "Dashboard".to_string()),
                ("database", database_name),
                ("status", "Active".to_string()),
            ])],
        }),

        "Sources" => {
            let mut rows = Vec::new();

            for line in read_lines(&sources_path()?) {
                if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
                    rows.push(row(vec![
                        ("source_id", value["metadata"]["source_id"].as_str().unwrap_or("").to_string()),
                        ("file_name", value["metadata"]["file_name"].as_str().unwrap_or("").to_string()),
                        ("stored_path", value["metadata"]["stored_path"].as_str().unwrap_or("").to_string()),
                        ("status", value["metadata"]["status"].as_str().unwrap_or("").to_string()),
                    ]));
                }
            }

            Ok(WorkspaceOutput {
                title: "Sources".to_string(),
                message: "Connected sources loaded.".to_string(),
                rows,
            })
        }

        "Data Drive" => {
            let data = data_dir()?;
            let mut rows = Vec::new();

            for item in ["imports", "sources.jsonl", "records.jsonl", "databases", "data_lake", "exports"] {
                let path = data.join(item);

                rows.push(row(vec![
                    ("item", item.to_string()),
                    ("location", path.to_string_lossy().to_string()),
                    ("size", format_bytes(size_of(&path))),
                    ("status", if path.exists() { "available".to_string() } else { "missing".to_string() }),
                ]));
            }

            Ok(WorkspaceOutput {
                title: "Data Drive".to_string(),
                message: "Data Drive storage loaded.".to_string(),
                rows,
            })
        }

        "Lakehouse" => {
            let mut rows = Vec::new();

            for layer in ["raw", "bronze", "silver", "gold"] {
                let path = layer_path(layer)?;
                let count = line_count(&path);

                rows.push(row(vec![
                    ("layer", layer.to_string()),
                    ("records", count.to_string()),
                    ("location", path.to_string_lossy().to_string()),
                    ("status", if count > 0 { "active".to_string() } else { "waiting".to_string() }),
                ]));
            }

            Ok(WorkspaceOutput {
                title: "Lakehouse".to_string(),
                message: "Lakehouse layers loaded.".to_string(),
                rows,
            })
        }

        "Raw" | "Bronze" | "Silver" | "Gold" => {
            let layer = action.to_lowercase();
            let path = layer_path(&layer)?;
            let count = line_count(&path);

            Ok(WorkspaceOutput {
                title: action.clone(),
                message: format!("{} layer loaded.", action),
                rows: vec![row(vec![
                    ("layer", action),
                    ("records", count.to_string()),
                    ("location", path.to_string_lossy().to_string()),
                    ("status", if count > 0 { "active".to_string() } else { "waiting".to_string() }),
                ])],
            })
        }

        "Pipelines" => {
            let (raw_to_bronze, bronze_to_silver, silver_to_gold) = pipeline_status()?;

            Ok(WorkspaceOutput {
                title: "Pipelines".to_string(),
                message: "Pipeline status loaded.".to_string(),
                rows: vec![
                    row(vec![("pipeline", "Raw → Bronze".to_string()), ("status", raw_to_bronze)]),
                    row(vec![("pipeline", "Bronze → Silver".to_string()), ("status", bronze_to_silver)]),
                    row(vec![("pipeline", "Silver → Gold".to_string()), ("status", silver_to_gold)]),
                ],
            })
        }

        "Queries" => Ok(WorkspaceOutput {
            title: "Queries".to_string(),
            message: "Available query actions loaded.".to_string(),
            rows: vec![
                row(vec![("query", "SELECT * FROM records LIMIT 100".to_string()), ("status", "ready".to_string())]),
                row(vec![("query", "SELECT COUNT(*) FROM sources".to_string()), ("status", "ready".to_string())]),
                row(vec![("query", "SELECT COUNT(*) FROM raw".to_string()), ("status", "ready".to_string())]),
            ],
        }),

        "Data Quality" => Ok(WorkspaceOutput {
            title: "Data Quality".to_string(),
            message: "Data quality calculated from raw records.".to_string(),
            rows: vec![row(vec![
                ("metric", "Raw record completeness".to_string()),
                ("score", data_quality()?),
                ("status", "calculated".to_string()),
            ])],
        }),

        "Run Pipeline" => {
            let raw_path = layer_path("raw")?;
            let bronze_path = layer_path("bronze")?;
            let silver_path = layer_path("silver")?;
            let gold_path = layer_path("gold")?;

            let raw_lines = read_lines(&raw_path);

            if raw_lines.is_empty() {
                log_event("[WARN] Pipeline waiting. No raw records found.")?;

                return Ok(WorkspaceOutput {
                    title: "Pipeline Status".to_string(),
                    message: "Pipeline waiting. No raw records found.".to_string(),
                    rows: vec![row(vec![
                        ("stage", "Raw → Bronze".to_string()),
                        ("records", "0".to_string()),
                        ("status", "Waiting".to_string()),
                    ])],
                });
            }

            fs::write(&bronze_path, raw_lines.join("\n") + "\n")
                .map_err(|error| format!("Unable to write bronze records: {}", error))?;

            let bronze_lines = read_lines(&bronze_path);

            fs::write(&silver_path, bronze_lines.join("\n") + "\n")
                .map_err(|error| format!("Unable to write silver records: {}", error))?;

            let silver_lines = read_lines(&silver_path);

            fs::write(&gold_path, silver_lines.join("\n") + "\n")
                .map_err(|error| format!("Unable to write gold records: {}", error))?;

            log_event("[INFO] Pipeline completed: raw -> bronze -> silver -> gold.")?;

            Ok(WorkspaceOutput {
                title: "Pipeline Status".to_string(),
                message: "Pipeline completed successfully.".to_string(),
                rows: vec![
                    row(vec![("stage", "Raw → Bronze".to_string()), ("records", line_count(&bronze_path).to_string()), ("status", "Success".to_string())]),
                    row(vec![("stage", "Bronze → Silver".to_string()), ("records", line_count(&silver_path).to_string()), ("status", "Success".to_string())]),
                    row(vec![("stage", "Silver → Gold".to_string()), ("records", line_count(&gold_path).to_string()), ("status", "Success".to_string())]),
                ],
            })
        }

        "Run Query" => {
            let mut rows = Vec::new();

            for line in read_lines(&records_path()?).into_iter().take(100) {
                if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
                    rows.push(row(vec![
                        ("source", value["source"].as_str().unwrap_or("").to_string()),
                        ("category", value["category"].as_str().unwrap_or("").to_string()),
                        ("sensor_type", value["sensor_type"].as_str().unwrap_or("").to_string()),
                        ("value", value["value"].as_str().unwrap_or("").to_string()),
                    ]));
                }
            }

            log_event("[INFO] Query executed: SELECT * FROM records LIMIT 100.")?;

            Ok(WorkspaceOutput {
                title: "Query Results".to_string(),
                message: format!("Query complete. {} records returned.", rows.len()),
                rows,
            })
        }

        "Logs" => Ok(WorkspaceOutput {
            title: "Logs".to_string(),
            message: "Logs loaded as spreadsheet rows.".to_string(),
            rows: log_rows()?,
        }),

        "Export" => {
            let export_path = data_dir()?.join("exports").join("workspace_logs_export.csv");
            let rows = log_rows()?;
            let headers = vec!["log_id", "log_file", "timestamp", "level", "action", "message", "source"];

            let mut csv = String::new();
            csv.push_str("\u{FEFF}");
            csv.push_str(&headers.join(","));
            csv.push('\n');

            for record in &rows {
                let line = headers
                    .iter()
                    .map(|key| csv_escape(record.get(*key).unwrap_or(&String::new())))
                    .collect::<Vec<String>>()
                    .join(",");

                csv.push_str(&line);
                csv.push('\n');
            }

            fs::write(&export_path, csv)
                .map_err(|error| format!("Unable to write export file: {}", error))?;

            log_event("[INFO] Export completed.")?;

            Ok(WorkspaceOutput {
                title: "Export".to_string(),
                message: "Spreadsheet export created for Microsoft Excel.".to_string(),
                rows: vec![row(vec![
                    ("export_file", export_path.to_string_lossy().to_string()),
                    ("format", "CSV".to_string()),
                    ("opens_with", "Microsoft Excel".to_string()),
                    ("status", "success".to_string()),
                ])],
            })
        }

        "Console" => Ok(WorkspaceOutput {
            title: "Console".to_string(),
            message: "Data Engine console ready.".to_string(),
            rows: vec![row(vec![("command", "Data Engine console".to_string()), ("status", "ready".to_string())])],
        }),

        "Settings" => Ok(WorkspaceOutput {
            title: "Settings".to_string(),
            message: "Settings loaded.".to_string(),
            rows: vec![row(vec![("setting", "Data Drive limit".to_string()), ("value", "500 MB".to_string())])],
        }),

        _ => Ok(WorkspaceOutput {
            title: action.clone(),
            message: format!("{} is not configured yet.", action),
            rows: vec![],
        }),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_user_locations,
            read_directory,
            connect_data,
            create_database,
            workspace_refresh,
            workspace_action
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
