# Data Platform — Button Function Summary

## Core Rule

Every button must follow this pattern:

Button click
→ validate input
→ run frontend function
→ run backend/data function
→ show loading state
→ return visible output
→ show success or error message
→ update stored records when needed

---

# 1. Navigation Buttons

## Workspace

Purpose:
Opens the main operating dashboard.

Frontend action:
setViewMode("workspace")

Backend/data action:
workspace_refresh()

Expected output:
Shows sources, raw records, databases, data quality, storage, pipeline status, recent ingestion, and output table.

Success message:
Workspace loaded.

Failure message:
Unable to load workspace status.

---

## Data

Purpose:
Opens the data setup screen.

Frontend action:
setViewMode("data")

Backend/data action:
No backend action until Choose File or Create Database is clicked.

Expected output:
Shows selected file, database name input, Data Drive location, and database location.

Success message:
Data setup ready.

Failure message:
No failure expected because this is a navigation action.

---

## Paige

Purpose:
Opens the Paige assistant/search screen.

Frontend action:
setViewMode("paige")

Backend/data action:
No backend action until Ask Question is clicked.

Expected output:
Shows question input, answer panel, source cards, and Open Source buttons.

Success message:
Paige ready.

Failure message:
No failure expected because this is a navigation action.

---

## Settings

Purpose:
Opens account and application settings.

Frontend action:
setViewMode("settings")

Backend/data action:
No backend action until Save Settings is clicked.

Expected output:
Shows display name, email, password/account options, storage limit, privacy, and app preferences.

Success message:
Settings ready.

Failure message:
No failure expected because this is a navigation action.

---

# 2. Data Setup Buttons

## Choose File

Purpose:
Selects a file from the user’s computer.

Frontend function:
chooseFile()

Backend/data function:
System file picker

What it does:
- Opens the system file picker.
- Stores the selected file path.
- Auto-generates a database name from the file name.
- Shows the selected file in the UI.

Success output:
- File selected.
- Selected file appears.
- Database name is auto-filled.

Failure output:
No file selected.

---

## Create Database

Purpose:
Connects the selected file and creates managed Data Engine storage.

Frontend function:
createDatabase()

Backend/data functions:
connect_data()
create_database()
workspace_refresh()

What it does:
- Validates that a file is selected.
- Validates that a database name exists.
- Stores the selected file in the Data Drive.
- Creates the database folder.
- Writes database metadata.
- Updates dashboard metrics.
- Displays the database result in the output table.

Success output:
- Database created.
- Database name appears.
- Database path appears.
- Dashboard metrics update.
- Output table shows database_name, database_path, source_file, and status.

Failure output:
- Choose a file first.
- Enter a database name.
- Database creation failed.

---

# 3. Workspace Buttons

## Run Pipeline

Purpose:
Processes stored data through the Data Platform pipeline.

Frontend function:
runPipeline()

Backend/data function:
workspace_action("Run Pipeline")

What it does:
- Checks that records or a database exist.
- Reads raw records.
- Processes data through Raw, Bronze, Silver, and Gold layers.
- Updates pipeline status.
- Displays pipeline results.

Pipeline flow:
Raw → Bronze → Silver → Gold

Success output:
- Pipeline complete.
- Pipeline status updates.
- Output table shows stage, record count, and status.

Failure output:
Create a database or add raw records before running the pipeline.

---

## Run Query

Purpose:
Queries stored Data Engine records.

Frontend function:
runQuery()

Backend/data function:
workspace_action("Run Query")

What it does:
- Checks that records or a database exist.
- Reads stored records.
- Returns query rows.
- Displays rows in the output table.

Success output:
- Query complete.
- Rows appear in the output table.

Failure output:
Create a database or add records before running a query.

---

# 4. Paige Buttons

## Ask Question

Purpose:
Sends a question to Paige and returns an answer.

Frontend function:
askQuestion()

Backend/data functions:
start_agent_worker()
submit_agent_task()
read_agent_output()

Advanced backend actions:
- Search online.
- Crawl useful result pages.
- Extract summaries.
- Clean source URLs.
- Store the answer as a record.
- Return source links.

What it does:
- Validates that the question is not empty.
- Starts Paige if needed.
- Writes the question to agent_input.json.
- Waits for agent_output.json.
- Reads the answer.
- Displays the answer and source cards.
- Stores the result in data/records.jsonl.

Success output:
- Answer ready.
- Answer text appears.
- Source cards appear.
- Open buttons appear for each source.

Failure output:
- Ask a question first.
- No new answer appeared yet.
- Something went wrong.

---

## Open Source

Purpose:
Opens a source link from Paige’s answer.

Frontend function:
openSource(url)

Backend/system function:
openUrl(url)

What it does:
- Validates the URL.
- Cleans the URL if needed.
- Opens the source website in the browser.

Success output:
Source opened.

Failure output:
This source does not have a valid link.

---

# 5. Settings Buttons

## Save Settings

Purpose:
Saves user and application preferences.

Frontend function:
saveSettings()

Future backend/data functions:
get_user_profile()
update_display_name()
update_email()
update_password()
update_login_credentials()
update_storage_limit()
update_privacy_settings()
update_app_preferences()

What it does:
- Validates settings fields.
- Updates display name.
- Updates email address.
- Updates storage preference.
- Later: updates password, login credentials, and privacy settings.
- Shows saved settings in the output table.

Success output:
- Settings updated.
- Output table shows display_name, email, storage_limit, and status.

Failure output:
- Enter a valid email address.
- Password could not be updated.
- Setting could not be saved.

---

# 6. System Feedback Elements

## Loading Overlay

Purpose:
Shows the app is working.

Used for:
- Creating database
- Running pipeline
- Running query
- Asking Paige
- Saving settings

---

## Success Toast

Purpose:
Confirms an action completed.

Examples:
- File selected.
- Database created.
- Pipeline complete.
- Query complete.
- Answer ready.
- Source opened.
- Settings updated.

---

## Status Panel

Purpose:
Shows the latest system state.

Examples:
- Ready.
- File selected.
- Database created.
- Running pipeline.
- Query complete.
- Answer ready.
- Settings updated.

---

# Final Backend Mapping

Workspace        → workspace_refresh()
Data             → setViewMode("data")
Paige            → setViewMode("paige")
Settings         → setViewMode("settings")

Choose File      → chooseFile()
Create Database  → connect_data() + create_database() + workspace_refresh()

Run Pipeline     → workspace_action("Run Pipeline")
Run Query        → workspace_action("Run Query")

Ask Question     → start_agent_worker() + submit_agent_task() + read_agent_output()
Open Source      → openUrl(url)

Save Settings    → update_user_settings() / future settings backend
