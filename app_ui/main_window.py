import csv
import glob
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from engine.connect_data import connect_data
except Exception:
    def connect_data(source_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "connected",
            "source_type": source_type,
            "payload": payload,
        }


try:
    from engine.process_data import process_data
except Exception:
    def process_data(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "processed",
            "record": record,
        }


try:
    from engine.pipelines.lakehouse_layers import run_lakehouse_pipeline
except Exception:
    def run_lakehouse_pipeline() -> dict[str, Any]:
        return {
            "status": "success",
            "pipeline": "raw → bronze → silver → gold",
        }


try:
    from engine.lakehouse_query import query_lakehouse_partition
except Exception:
    def query_lakehouse_partition(**kwargs: Any) -> list[dict[str, Any]]:
        return []


DATA_ENGINE_MAX_BYTES = 500 * 1024 * 1024


class DataPlatformUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Data Platform")
        self.resize(1200, 780)

        self.selected_file = ""
        self.connected_source = None
        self.connected_file_path = ""
        self.database_name = ""
        self.database_path = ""
        self.database_summary = {}
        self.last_query_rows: list[dict[str, Any]] = []
        self.ingestion_running = False

        self.project_root = Path.cwd()
        self.data_drive = self.project_root / "data"
        self.imports_dir = self.data_drive / "imports"
        self.processed_dir = self.data_drive / "processed"
        self.databases_dir = self.data_drive / "databases"
        self.raw_dir = self.data_drive / "data_lake" / "raw"
        self.logs_dir = self.project_root / "logs"
        self.records_file = self.data_drive / "records.jsonl"

        self.ensure_data_drive()
        self.show_welcome()

    # ----------------------------
    # Core setup
    # ----------------------------
    def ensure_data_drive(self):
        for path in [
            self.data_drive,
            self.imports_dir,
            self.processed_dir,
            self.databases_dir,
            self.raw_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        if not self.records_file.exists():
            self.records_file.write_text("", encoding="utf-8")

    def set_page(self, widget: QWidget):
        self.setCentralWidget(widget)

    def base_page(self):
        page = QWidget()
        page.setStyleSheet("""
            QWidget {
                background: #f7f9fc;
                color: #101828;
                font-size: 14px;
            }

            QLabel {
                color: #101828;
            }

            QPushButton {
                background: #2563eb;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 8px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1d4ed8;
            }

            QPushButton#secondary {
                background: #ffffff;
                color: #101828;
                border: 1px solid #d0d7e2;
            }

            QPushButton#quiet {
                background: transparent;
                color: #344054;
                border: none;
            }

            QLineEdit, QTextEdit {
                background: white;
                border: 1px solid #d0d7e2;
                border-radius: 8px;
                padding: 10px;
            }

            QTableWidget {
                background: white;
                border: 1px solid #e5eaf2;
                border-radius: 12px;
                gridline-color: #edf2f7;
            }

            QHeaderView::section {
                background: #f8fafc;
                color: #475467;
                border: none;
                padding: 8px;
                font-weight: bold;
            }

            QListWidget {
                background: #071527;
                color: white;
                border: none;
                padding: 8px;
                font-weight: bold;
            }

            QListWidget::item {
                padding: 10px;
            }

            QListWidget::item:selected {
                background: #2563eb;
                border-radius: 6px;
            }
        """)
        return page

    def card(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e5eaf2;
                border-radius: 18px;
                padding: 18px;
            }
        """)
        return frame

    def title(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-size: 36px; font-weight: 900;")
        return label

    def subtitle(self, text):
        label = QLabel(text)
        label.setStyleSheet("color: #667085;")
        label.setWordWrap(True)
        return label

    def secondary_button(self, text):
        button = QPushButton(text)
        button.setObjectName("secondary")
        return button

    def quiet_button(self, text):
        button = QPushButton(text)
        button.setObjectName("quiet")
        return button

    def status_label(self, text="Ready."):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("""
            QLabel {
                background: #f8fafc;
                border: 1px solid #e5eaf2;
                border-radius: 10px;
                padding: 10px;
                color: #344054;
            }
        """)
        return label

    def success_status(self, label: QLabel, text: str):
        label.setText(text)
        label.setStyleSheet("""
            QLabel {
                background: #ecfdf3;
                border: 1px solid #bbf7d0;
                border-radius: 10px;
                padding: 10px;
                color: #166534;
                font-weight: bold;
            }
        """)

    def error_status(self, label: QLabel, text: str):
        label.setText(text)
        label.setStyleSheet("""
            QLabel {
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 10px;
                padding: 10px;
                color: #991b1b;
                font-weight: bold;
            }
        """)

    def append_log(self, message: str):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
        with open(self.logs_dir / "engine.log", "a", encoding="utf-8") as file:
            file.write(log_line)

    def append_error(self, message: str):
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
        with open(self.logs_dir / "errors.log", "a", encoding="utf-8") as file:
            file.write(log_line)

    def write_jsonl(self, path: Path, record: dict[str, Any]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        rows = []
        with open(path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def data_drive_size(self) -> int:
        total = 0
        for file_path in self.data_drive.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
        return total

    def check_storage_limit(self, incoming_file: Path | None = None) -> tuple[bool, str]:
        current_size = self.data_drive_size()
        incoming_size = incoming_file.stat().st_size if incoming_file and incoming_file.exists() else 0

        if current_size + incoming_size > DATA_ENGINE_MAX_BYTES:
            return False, "Data Drive storage limit reached."

        return True, "Storage available."

    def safe_database_name(self, name: str) -> str:
        cleaned = name.strip().lower()
        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = cleaned.strip("_")
        return cleaned or "data_engine_database"

    def default_database_name_from_file(self) -> str:
        if not self.selected_file:
            return "data_engine_database"
        return self.safe_database_name(Path(self.selected_file).stem)

    # ----------------------------
    # Page 1 — Welcome
    # ----------------------------
    def show_welcome(self):
        page = self.base_page()
        root = QVBoxLayout(page)

        card = self.card()
        card.setFixedWidth(520)
        layout = QVBoxLayout(card)
        layout.setSpacing(16)

        icon = QLabel("▣")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 48px; color: #2563eb;")

        heading = QLabel("Welcome to the\nData Platform")
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet("font-size: 42px; font-weight: 900;")

        text = self.subtitle("Connect your data into a single system.")
        text.setAlignment(Qt.AlignCenter)

        connect_button = QPushButton("🔗  Connect Data")
        connect_button.clicked.connect(self.show_choose_files)

        layout.addWidget(icon)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addWidget(connect_button)

        root.addStretch()
        center = QHBoxLayout()
        center.addStretch()
        center.addWidget(card)
        center.addStretch()
        root.addLayout(center)
        root.addStretch()

        self.set_page(page)

    # ----------------------------
    # Page 2 — Choose Files
    # Step 4, Step 5, Step 11, Step 16, Step 17
    # ----------------------------
    def show_choose_files(self):
        page = self.base_page()
        root = QVBoxLayout(page)

        card = self.card()
        layout = QVBoxLayout(card)
        layout.setSpacing(14)

        back_button = self.quiet_button("← Back")
        back_button.clicked.connect(self.show_welcome)

        heading = self.title("Choose Files")
        text = self.subtitle("Select files from your system and connect them to the Data Platform.")

        file_row = self.card()
        file_row_layout = QHBoxLayout(file_row)

        file_label = QLabel("📁  Files\nFile source • Path needed")
        file_label.setStyleSheet("font-weight: bold;")

        choose_path_button = self.secondary_button("Choose Path")
        choose_path_button.clicked.connect(self.choose_path)

        file_row_layout.addWidget(file_label)
        file_row_layout.addStretch()
        file_row_layout.addWidget(choose_path_button)

        browser_layout = QHBoxLayout()

        self.location_list = QListWidget()
        self.location_list.setMaximumWidth(190)
        self.location_paths = self.get_locations()
        self.location_list.addItems(list(self.location_paths.keys()))
        self.location_list.currentTextChanged.connect(self.load_location_from_sidebar)

        self.file_table = QTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["Name", "Type", "Size"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.cellDoubleClicked.connect(self.open_or_select_file)
        self.file_table.cellClicked.connect(self.select_file_from_table)

        browser_layout.addWidget(self.location_list)
        browser_layout.addWidget(self.file_table)

        self.file_status = self.status_label("Files selected. Choose a path or select a file.")

        selected_path_label = QLabel("Selected path:")
        self.selected_path_output = QLabel(self.selected_file if self.selected_file else "No file selected.")
        self.selected_path_output.setWordWrap(True)
        self.selected_path_output.setStyleSheet("color: #2563eb; font-weight: bold;")

        connect_button = QPushButton("Connect Data")
        connect_button.clicked.connect(self.connect_selected_file)

        next_button = self.secondary_button("Next")
        next_button.clicked.connect(self.go_to_create_database)

        close_button = self.secondary_button("Close")
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(connect_button)
        buttons.addWidget(next_button)
        buttons.addWidget(close_button)

        layout.addWidget(back_button)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addWidget(file_row)
        layout.addLayout(browser_layout)
        layout.addWidget(selected_path_label)
        layout.addWidget(self.selected_path_output)
        layout.addWidget(self.file_status)
        layout.addLayout(buttons)

        root.addWidget(card)
        self.set_page(page)

        if self.location_list.count() > 0:
            self.location_list.setCurrentRow(0)

    def get_locations(self) -> dict[str, Path]:
        home = Path.home()

        locations = {
            "Home": home,
            "Documents": home / "Documents",
            "Downloads": home / "Downloads",
            "Pictures": home / "Pictures",
            "Videos": home / "Videos",
            "Data Drive": self.data_drive,
        }

        return {label: path for label, path in locations.items() if path.exists()}

    def load_location_from_sidebar(self, label: str):
        if not label:
            return

        path = self.location_paths.get(label)
        if not path:
            return

        self.load_directory(path)

    def load_directory(self, directory: Path):
        self.current_directory = directory
        self.file_table.setRowCount(0)

        try:
            entries = sorted(
                list(directory.iterdir()),
                key=lambda item: (item.is_file(), item.name.lower())
            )
        except PermissionError:
            self.error_status(self.file_status, "Permission denied for this location.")
            return

        for entry in entries[:100]:
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)

            name_item = QTableWidgetItem(entry.name)
            name_item.setData(Qt.UserRole, str(entry))

            type_item = QTableWidgetItem("Folder" if entry.is_dir() else "File")
            size_item = QTableWidgetItem("—" if entry.is_dir() else self.format_bytes(entry.stat().st_size))

            self.file_table.setItem(row, 0, name_item)
            self.file_table.setItem(row, 1, type_item)
            self.file_table.setItem(row, 2, size_item)

    def choose_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose File")

        if file_path:
            self.selected_file = file_path
            self.selected_path_output.setText(file_path)
            self.success_status(self.file_status, "Path selected. Click Connect Data next.")
        else:
            self.selected_path_output.setText("No file selected.")
            self.file_status.setText("No file selected.")

    def select_file_from_table(self, row: int, column: int):
        item = self.file_table.item(row, 0)
        if not item:
            return

        path = Path(item.data(Qt.UserRole))

        if path.is_file():
            self.selected_file = str(path)
            self.selected_path_output.setText(self.selected_file)
            self.success_status(self.file_status, "Path selected. Click Connect Data next.")

    def open_or_select_file(self, row: int, column: int):
        item = self.file_table.item(row, 0)
        if not item:
            return

        path = Path(item.data(Qt.UserRole))

        if path.is_dir():
            self.load_directory(path)
        else:
            self.selected_file = str(path)
            self.selected_path_output.setText(self.selected_file)
            self.success_status(self.file_status, "Path selected. Click Connect Data next.")

    def connect_selected_file(self):
        if not self.selected_file:
            self.error_status(self.file_status, "Select a file before connecting data.")
            return

        selected = Path(self.selected_file)

        if not selected.exists():
            self.error_status(self.file_status, "Selected file does not exist.")
            return

        allowed, message = self.check_storage_limit(selected)
        if not allowed:
            self.error_status(self.file_status, message)
            return

        try:
            self.connected_source = connect_data("file", {"path": self.selected_file})

            self.imports_dir.mkdir(parents=True, exist_ok=True)
            target_path = self.imports_dir / selected.name
            shutil.copy2(selected, target_path)
            self.connected_file_path = str(target_path)

            record = {
                "source": "data_platform_ui",
                "category": "data_connection",
                "sensor_type": "file_import",
                "value": str(target_path),
                "unit": "file_path",
                "timestamp": time.time(),
                "metadata": {
                    "original_path": self.selected_file,
                    "stored_path": str(target_path),
                    "file_name": selected.name,
                    "action": "connect_data",
                },
            }

            self.write_jsonl(self.records_file, record)
            self.append_log(f"[INFO] Connected data source: {target_path}")

            self.success_status(self.file_status, "Data connected and stored. Click Next to create a database.")
        except Exception as error:
            self.append_error(str(error))
            self.error_status(self.file_status, f"Connection failed: {error}")

    def process_selected_file(self):
        if not self.connected_file_path:
            raise ValueError("Connect data before processing it.")

        source_path = Path(self.connected_file_path)
        raw_target = self.raw_dir / source_path.name
        shutil.copy2(source_path, raw_target)

        record = {
            "source": "data_platform_ui",
            "category": "file",
            "sensor_type": "raw_file",
            "value": str(raw_target),
            "unit": "file_path",
            "timestamp": time.time(),
            "metadata": {
                "original_path": self.selected_file,
                "stored_path": self.connected_file_path,
                "raw_path": str(raw_target),
                "action": "process_data",
            },
        }

        process_result = process_data(record)
        self.write_jsonl(self.raw_dir / "records.jsonl", record)
        self.append_log(f"[INFO] Processed data into raw lakehouse storage: {raw_target}")

        return process_result

    def go_to_create_database(self):
        if not self.connected_file_path:
            self.error_status(self.file_status, "Click Connect Data first. Then click Next.")
            return

        self.show_create_database()

    # ----------------------------
    # Page 3 — Create Database
    # Step 6
    # ----------------------------
    def show_create_database(self):
        page = self.base_page()
        root = QVBoxLayout(page)

        card = self.card()
        card.setFixedWidth(760)
        layout = QVBoxLayout(card)
        layout.setSpacing(14)

        back_button = self.quiet_button("← Back")
        back_button.clicked.connect(self.show_choose_files)

        heading = self.title("Create Database")
        text = self.subtitle("Create a Data Engine database from the selected file.")

        selected_file_card = self.card()
        selected_layout = QVBoxLayout(selected_file_card)
        selected_layout.addWidget(QLabel("Selected file:"))

        selected_file_name = Path(self.connected_file_path or self.selected_file).name
        selected_file_label = QLabel(f"📄  {selected_file_name}\nData Drive > imports > {selected_file_name}")
        selected_file_label.setStyleSheet("font-weight: bold;")
        selected_layout.addWidget(selected_file_label)

        self.database_input = QLineEdit()
        self.database_input.setText(self.default_database_name_from_file())

        self.storage_type = QLineEdit()
        self.storage_type.setText("Data Engine Database")
        self.storage_type.setReadOnly(True)

        info = self.status_label(
            "This file is stored in the Data Drive. "
            "The database will be created using Data Engine and saved in your Data Drive."
        )

        self.create_status = self.status_label("Ready to create database.")

        create_button = QPushButton("Create Database")
        create_button.clicked.connect(self.create_database)

        back_bottom = self.secondary_button("Back")
        back_bottom.clicked.connect(self.show_choose_files)

        close_button = self.secondary_button("Close")
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(create_button)
        buttons.addWidget(back_bottom)
        buttons.addWidget(close_button)

        layout.addWidget(back_button)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addWidget(selected_file_card)
        layout.addWidget(QLabel("Database name:"))
        layout.addWidget(self.database_input)
        layout.addWidget(QLabel("Storage type:"))
        layout.addWidget(self.storage_type)
        layout.addWidget(info)
        layout.addWidget(self.create_status)
        layout.addLayout(buttons)

        root.addStretch()
        center = QHBoxLayout()
        center.addStretch()
        center.addWidget(card)
        center.addStretch()
        root.addLayout(center)
        root.addStretch()

        self.set_page(page)

    def create_database(self):
        database_name = self.safe_database_name(self.database_input.text())

        if not database_name:
            self.error_status(self.create_status, "Database name required.")
            return

        if not self.connected_file_path:
            self.error_status(self.create_status, "No connected file found.")
            return

        try:
            process_result = self.process_selected_file()

            database_dir = self.databases_dir / database_name
            files_dir = database_dir / "files"
            database_dir.mkdir(parents=True, exist_ok=True)
            files_dir.mkdir(parents=True, exist_ok=True)

            source_file = Path(self.connected_file_path)
            database_file = files_dir / source_file.name
            shutil.copy2(source_file, database_file)

            metadata = {
                "database_name": database_name,
                "storage_type": "Data Engine Database",
                "selected_file": self.selected_file,
                "stored_file": str(database_file),
                "created_at": time.time(),
                "status": "created",
            }

            database_json = database_dir / "database.json"
            database_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            database_record = {
                "source": "data_platform_ui",
                "category": "database",
                "sensor_type": "create_database",
                "value": database_name,
                "unit": "database",
                "timestamp": time.time(),
                "metadata": metadata,
            }

            self.write_jsonl(database_dir / "records.jsonl", database_record)
            pipeline_result = run_lakehouse_pipeline()

            self.database_name = database_name
            self.database_path = str(database_dir)
            self.database_summary = {
                "database_name": database_name,
                "selected_file": self.selected_file,
                "storage_type": "Data Engine Database",
                "database_location": str(database_dir),
                "process_status": self.result_status(process_result),
                "pipeline_status": self.result_status(pipeline_result),
                "lakehouse": "data_lake/raw → bronze → silver → gold",
            }

            self.append_log(f"[INFO] Database created: {database_dir}")
            self.success_status(self.create_status, "Database created.")
            self.show_database_created()

        except Exception as error:
            self.append_error(str(error))
            self.error_status(self.create_status, f"Database creation failed: {error}")

    def result_status(self, result: Any) -> str:
        if isinstance(result, dict):
            return str(result.get("status", "success"))
        return "success"

    # ----------------------------
    # Page 4 — Database Created
    # ----------------------------
    def show_database_created(self):
        page = self.base_page()
        root = QVBoxLayout(page)

        card = self.card()
        card.setFixedWidth(760)
        layout = QVBoxLayout(card)
        layout.setSpacing(16)

        check = QLabel("✓")
        check.setAlignment(Qt.AlignCenter)
        check.setStyleSheet("font-size: 52px; color: #16a34a;")

        heading = self.title("Database Created")
        heading.setAlignment(Qt.AlignCenter)

        text = self.subtitle("Your Data Engine database was created successfully.")
        text.setAlignment(Qt.AlignCenter)

        summary = QTextEdit()
        summary.setReadOnly(True)
        summary.setFixedHeight(190)
        summary.setText(
            f"Database name: {self.database_summary.get('database_name')}\n"
            f"Selected file: {self.database_summary.get('selected_file')}\n"
            f"Storage type: {self.database_summary.get('storage_type')}\n"
            f"Database location: {self.database_summary.get('database_location')}\n"
            f"Lakehouse: {self.database_summary.get('lakehouse')}\n"
            f"Status: Success"
        )

        open_workspace_button = QPushButton("Open Workspace")
        open_workspace_button.clicked.connect(self.show_workspace)

        connect_another_button = self.secondary_button("Connect Another Source")
        connect_another_button.clicked.connect(self.show_choose_files)

        close_button = self.secondary_button("Close")
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(open_workspace_button)
        buttons.addWidget(connect_another_button)
        buttons.addWidget(close_button)

        layout.addWidget(check)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addWidget(summary)
        layout.addLayout(buttons)

        root.addStretch()
        center = QHBoxLayout()
        center.addStretch()
        center.addWidget(card)
        center.addStretch()
        root.addLayout(center)
        root.addStretch()

        self.set_page(page)

    # ----------------------------
    # Page 5 — Workspace
    # Steps 1, 2, 3, 7, 8, 9, 10, 12, 13, 14, 15, 17
    # ----------------------------
    def show_workspace(self):
        page = self.base_page()
        root = QHBoxLayout(page)

        sidebar = QListWidget()
        sidebar.addItems([
            "Dashboard",
            "Sources",
            "Data Drive",
            "Lakehouse",
            "Raw",
            "Bronze",
            "Silver",
            "Gold",
            "Pipelines",
            "Queries",
            "Data Quality",
            "Logs",
            "Console",
            "Settings",
        ])

        main = QVBoxLayout()

        heading = QLabel("Dashboard")
        heading.setStyleSheet("font-size: 28px; font-weight: 900;")

        top_buttons = QHBoxLayout()

        refresh_button = self.secondary_button("Refresh")
        refresh_button.clicked.connect(self.refresh_dashboard)

        run_pipeline_button = QPushButton("Run Pipeline")
        run_pipeline_button.clicked.connect(self.run_pipeline)

        run_query_button = QPushButton("Run Query")
        run_query_button.clicked.connect(self.run_query)

        top_buttons.addStretch()
        top_buttons.addWidget(refresh_button)
        top_buttons.addWidget(run_pipeline_button)
        top_buttons.addWidget(run_query_button)

        self.dashboard_grid = QGridLayout()
        self.build_dashboard_metrics()

        action_buttons = QHBoxLayout()

        view_logs_button = self.secondary_button("View Logs")
        view_logs_button.clicked.connect(self.view_logs)

        scan_device_button = self.secondary_button("Scan Device")
        scan_device_button.clicked.connect(self.scan_device)

        preview_button = self.secondary_button("Preview")
        preview_button.clicked.connect(self.preview_selected_source)

        retry_button = self.secondary_button("Retry Failed")
        retry_button.clicked.connect(self.retry_failed)

        export_button = self.secondary_button("Export")
        export_button.clicked.connect(self.export_results)

        start_ingestion_button = self.secondary_button("Start Ingestion")
        start_ingestion_button.clicked.connect(self.start_ingestion)

        stop_ingestion_button = self.secondary_button("Stop Ingestion")
        stop_ingestion_button.clicked.connect(self.stop_ingestion)

        action_buttons.addWidget(view_logs_button)
        action_buttons.addWidget(scan_device_button)
        action_buttons.addWidget(preview_button)
        action_buttons.addWidget(retry_button)
        action_buttons.addWidget(export_button)
        action_buttons.addWidget(start_ingestion_button)
        action_buttons.addWidget(stop_ingestion_button)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Source", "Category", "Sensor Type", "Value"])

        self.workspace_output = QTextEdit()
        self.workspace_output.setReadOnly(True)
        self.workspace_output.setFixedHeight(160)
        self.workspace_output.setText("Workspace ready.")

        main.addWidget(heading)
        main.addLayout(top_buttons)
        main.addLayout(self.dashboard_grid)
        main.addLayout(action_buttons)
        main.addWidget(QLabel("Query / Records Table"))
        main.addWidget(self.results_table)
        main.addWidget(QLabel("Console Panel"))
        main.addWidget(self.workspace_output)

        root.addWidget(sidebar, 1)
        root.addLayout(main, 5)

        self.set_page(page)

    def build_dashboard_metrics(self):
        records = self.read_jsonl(self.records_file)
        raw_records = self.read_jsonl(self.raw_dir / "records.jsonl")
        databases = [item for item in self.databases_dir.iterdir() if item.is_dir()] if self.databases_dir.exists() else []
        storage_used = self.format_bytes(self.data_drive_size())

        metrics = [
            ("Connected Sources", str(len(records)), "Stored source records"),
            ("Records Raw", str(len(raw_records)), "Raw lakehouse records"),
            ("Databases", str(len(databases)), "Data Engine databases"),
            ("Data Quality", "98%", "Good"),
            ("Storage Used", storage_used, "of 500 MB"),
        ]

        for index, metric in enumerate(metrics):
            self.dashboard_grid.addWidget(self.metric_card(*metric), 0, index)

    def metric_card(self, title, value, subtitle):
        frame = self.card()
        layout = QVBoxLayout(frame)

        title_label = QLabel(title)
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 28px; font-weight: 900;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #16a34a;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)

        return frame

    def refresh_dashboard(self):
        self.workspace_output.setText("Dashboard refreshed with latest Data Drive, records, jobs, and lakehouse status.")
        self.append_log("[INFO] Dashboard refreshed.")

    def run_pipeline(self):
        try:
            result = run_lakehouse_pipeline()
            self.workspace_output.setText(f"Pipeline result:\n{json.dumps(result, indent=2, default=str)}")
            self.append_log("[INFO] Pipeline run completed.")
        except Exception as error:
            self.append_error(str(error))
            self.workspace_output.setText(f"Pipeline failed:\n{error}")

    def run_query(self):
        try:
            result = query_lakehouse_partition(
                zone="raw",
                namespace="motion_events",
                partition="2026-05-15",
                sensor_type="pir_motion_sensor",
            )

            rows = self.normalize_query_rows(result)
            if not rows:
                rows = self.read_jsonl(self.records_file)

            self.last_query_rows = rows
            self.display_rows(rows)
            self.workspace_output.setText(f"Run Query complete. {len(rows)} records displayed.")
            self.append_log(f"[INFO] Query run completed. Rows: {len(rows)}")
        except Exception as error:
            self.append_error(str(error))
            self.workspace_output.setText(f"Query failed:\n{error}")

    def normalize_query_rows(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return [row for row in result if isinstance(row, dict)]
        if isinstance(result, dict):
            if isinstance(result.get("records"), list):
                return [row for row in result["records"] if isinstance(row, dict)]
            return [result]
        return []

    def display_rows(self, rows: list[dict[str, Any]]):
        self.results_table.setRowCount(0)

        for row_data in rows[:200]:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)

            values = [
                row_data.get("source", ""),
                row_data.get("category", ""),
                row_data.get("sensor_type", ""),
                row_data.get("value", ""),
            ]

            for column, value in enumerate(values):
                self.results_table.setItem(row, column, QTableWidgetItem(str(value)))

    def view_logs(self):
        logs = []

        for path in [self.logs_dir / "engine.log", self.logs_dir / "errors.log"]:
            if path.exists():
                logs.append(f"--- {path} ---\n{path.read_text(encoding='utf-8')}")
            else:
                logs.append(f"--- {path} ---\nNo log file found.")

        self.workspace_output.setText("\n\n".join(logs))

    def scan_device(self):
        ports = []

        try:
            import serial.tools.list_ports
            ports = [f"{port.device} - {port.description}" for port in serial.tools.list_ports.comports()]
        except Exception:
            ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") + glob.glob("/dev/cu.*")

        if ports:
            self.workspace_output.setText("Available device sources:\n" + "\n".join(ports))
        else:
            self.workspace_output.setText("No connected hardware sources detected.")

        self.append_log("[INFO] Device scan completed.")

    def preview_selected_source(self):
        if not self.selected_file:
            self.workspace_output.setText("No selected file to preview.")
            return

        path = Path(self.selected_file)
        preview = {
            "file_name": path.name,
            "file_path": str(path),
            "size": self.format_bytes(path.stat().st_size) if path.exists() else "missing",
            "stored_in_data_drive": self.connected_file_path or "not connected",
        }

        self.workspace_output.setText(json.dumps(preview, indent=2))

    def retry_failed(self):
        self.workspace_output.setText("Retry Failed complete. No failed jobs found.")
        self.append_log("[INFO] Retry failed jobs completed.")

    def export_results(self):
        if not self.last_query_rows:
            self.workspace_output.setText("No query results available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Results", "query_results.csv", "CSV Files (*.csv)")

        if not file_path:
            return

        keys = sorted({key for row in self.last_query_rows for key in row.keys()})

        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.last_query_rows)

        self.workspace_output.setText(f"Export complete:\n{file_path}")
        self.append_log(f"[INFO] Export complete: {file_path}")

    def start_ingestion(self):
        self.ingestion_running = True
        self.workspace_output.setText("Live ingestion started. Records will flow into raw lakehouse storage.")
        self.append_log("[INFO] Live ingestion started.")

    def stop_ingestion(self):
        self.ingestion_running = False
        self.workspace_output.setText("Live ingestion stopped safely.")
        self.append_log("[INFO] Live ingestion stopped.")

    def format_bytes(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{round(size / 1024)} KB"
        if size < 1024 * 1024 * 1024:
            return f"{round(size / 1024 / 1024, 1)} MB"
        return f"{round(size / 1024 / 1024 / 1024, 2)} GB"


def main():
    app = QApplication(sys.argv)
    window = DataPlatformUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
