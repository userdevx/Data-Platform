"""DataWorc model-driven application generation.

Generates actual Python applications with the registered local model.
Application Engineering performs compilation, testing, execution,
repair, and checkpointing. Generated code does not run on the host.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.application.automatic_model_request_action import (
    process_automatic_model_request,
)
from engine.application_generation.build_events import emit_event
from engine.application_engineering.models import (
    EngineeringPlan,
    PlannedFileChange,
    RepositoryInspection,
    ValidationStep,
)
from engine.application_engineering.runtime import (
    ApplicationEngineeringRuntime,
)
from engine.data_engine.record_writer import DataEngineRecordWriter
from engine.tools.file_tools import (
    MANAGED_APPLICATION_ROOT,
    register_managed_workspace,
    release_managed_workspace,
)


# These scripts belong to DataWorc, not to the generation model.
# Application Engineering executes them in gVisor.
CHECK_FILES = {
    "_dataworc_compile.py": '''
from pathlib import Path

root = Path(__file__).resolve().parent

for path in sorted(root.rglob("*.py")):
    if ".git" in path.parts:
        continue

    compile(
        path.read_text(encoding="utf-8"),
        str(path),
        "exec",
    )

    print("COMPILED", path.relative_to(root))
''',

    "_dataworc_test.py": '''
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

suite = unittest.defaultTestLoader.discover(
    str(root / "tests"),
    pattern="test_*.py",
)

if suite.countTestCases() == 0:
    raise SystemExit("No generated tests found")

result = unittest.TextTestRunner(
    stream=sys.stdout,
    verbosity=2,
).run(suite)

raise SystemExit(0 if result.wasSuccessful() else 1)
''',
}


# Independent acceptance contract for the first real milestone.
# This is written by DataWorc; the model cannot rewrite this test.
FITNESS_ACCEPTANCE = '''
import json
import math
import tempfile
import unittest
from pathlib import Path

from tracker import FitnessTracker


class DataWorcFitnessAcceptance(unittest.TestCase):

    def test_real_persistence_totals_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fitness.json"

            tracker = FitnessTracker(path)

            tracker.add_activity(3.0, 300.0, 180.0)
            tracker.add_activity(2.0, 210.0, 179.0)

            self.assertEqual(len(tracker.history()), 2)

            totals = tracker.totals()

            self.assertTrue(
                math.isclose(totals["distance_miles"], 5.0)
            )

            self.assertTrue(
                math.isclose(totals["calories_burned"], 510.0)
            )

            tracker.save()

            stored = json.loads(
                path.read_text(encoding="utf-8")
            )

            self.assertIsInstance(stored, list)
            self.assertGreaterEqual(len(stored), 6)

            for measurement in stored:
                self.assertEqual(
                    set(measurement),
                    {
                        "source",
                        "category",
                        "data_type",
                        "value",
                        "unit",
                    },
                )

            restored = FitnessTracker(path)
            restored.load()

            self.assertEqual(len(restored.history()), 2)
            self.assertEqual(restored.totals(), totals)

            with self.assertRaises((TypeError, ValueError)):
                restored.add_activity(-1.0, 20.0, 180.0)

            with self.assertRaises((TypeError, ValueError)):
                restored.add_activity(1.0, -20.0, 180.0)

            with self.assertRaises((TypeError, ValueError)):
                restored.add_activity(1.0, 20.0, float("nan"))


if __name__ == "__main__":
    unittest.main()
'''


VALIDATION_STEPS = (
    (
        "compile: parse every generated Python file",
        "python _dataworc_compile.py",
    ),
    (
        "test: generated tests and independent acceptance",
        "python _dataworc_test.py",
    ),
    (
        "run: application demo executes without input",
        "python main.py",
    ),
)

MAX_FILES = 6
MAX_REPAIRS = 3


def clean_json(text: str) -> dict[str, Any]:
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if not lines or lines[-1].strip() != "```":
            raise ValueError("Incomplete model JSON")

        text = "\n".join(lines[1:-1]).strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Model manifest JSON invalid: {text[:280]!r}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("Manifest must be a JSON object")

    return result


def source_path(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing generated file path")

    path = Path(name)

    if (
        path.is_absolute()
        or ".." in path.parts
        or ".git" in path.parts
        or any(part.startswith(".") for part in path.parts)
        or len(path.parts) > 2
        or (len(path.parts) == 2 and path.parts[0] != "tests")
        or not name.endswith(".py")
        or path.name.startswith("_dataworc")
        or name == "tests/test_dataworc_acceptance.py"
    ):
        raise ValueError(
            f"Unapproved generated file path: {name}"
        )

    return name


def validate_manifest(
    value: dict[str, Any],
    *,
    fitness: bool,
) -> dict[str, Any]:

    for field in ("application_name", "summary"):
        if (
            not isinstance(value.get(field), str)
            or not value[field].strip()
        ):
            raise ValueError(f"Manifest requires {field}")

    planned = value.get("files")

    if (
        not isinstance(planned, list)
        or not 2 <= len(planned) <= MAX_FILES
    ):
        raise ValueError("Manifest must plan 2-6 source files")

    files: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in planned:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("purpose"), str)
            or not item["purpose"].strip()
        ):
            raise ValueError(
                "Every planned file needs a purpose"
            )

        name = source_path(item.get("path"))

        if name in seen:
            raise ValueError(
                f"Duplicate planned file: {name}"
            )

        seen.add(name)

        files.append({
            "path": name,
            "purpose": item["purpose"].strip(),
        })

    if "main.py" not in seen:
        raise ValueError("Manifest requires main.py")

    if not any(
        name.startswith("tests/test_")
        for name in seen
    ):
        raise ValueError(
            "Manifest requires tests/test_*.py"
        )

    if fitness and "tracker.py" not in seen:
        raise ValueError(
            "Fitness acceptance requires tracker.py"
        )

    files.sort(
        key=lambda item: item["path"].startswith("tests/")
    )

    return {
        "application_name": value["application_name"].strip(),
        "summary": value["summary"].strip(),
        "files": files,
    }


def clean_source(text: str, path: str) -> str:
    lines = text.strip().splitlines()

    if lines and lines[0].strip().startswith("```"):
        if lines[-1].strip() != "```":
            raise ValueError(
                f"Incomplete generated source: {path}"
            )

        lines = lines[1:-1]

    source = "\n".join(lines).strip() + "\n"

    if not source.strip() or len(source) > 60000:
        raise ValueError(
            f"Empty or oversized source: {path}"
        )

    return source


class ApplicationGenerationCapability:
    name = "application_generation"

    @staticmethod
    def _record(
        writer,
        request_id: str,
        application_id: str,
        kind: str,
        value: dict,
    ):
        writer.write(
            source="application_generation",
            category="application_generation",
            data_type=kind,
            unit="record",
            value={
                "request_id": request_id,
                "application_id": application_id,
                **value,
            },
        )

    @staticmethod
    def _engineering_plan(
        manifest,
        inspection,
        requirement_id,
        existing,
    ):
        items = manifest["files"] + [
            {
                "path": path,
                "purpose": "DataWorc engineering verification",
            }
            for path in CHECK_FILES
        ]

        changes = tuple(
            PlannedFileChange(
                path=item["path"],
                operation=(
                    "modify"
                    if item["path"] in existing
                    else "create"
                ),
                purpose=item["purpose"],
            )
            for item in items
        )

        validations = tuple(
            ValidationStep(
                description=description,
                command=command,
            )
            for description, command in VALIDATION_STEPS
        )

        return EngineeringPlan.create(
            requirement_id=requirement_id,
            inspection_id=inspection.inspection_id,
            summary=manifest["summary"],
            planned_changes=changes,
            validation_steps=validations,
            risks=(
                "Model-authored tests require independent acceptance.",
            ),
        )

    def execute(self, request, instance) -> dict:
        permissions = instance.definition.permissions

        if not (
            permissions.write_records
            and permissions.run_approved_commands
        ):
            return {
                "capability": self.name,
                "source": self.name,
                "status": "rejected",
                "answer": (
                    "Application Engineering requires approved "
                    "command and record-write permissions."
                ),
                "data": {},
                "errors": ["required permissions not granted"],
            }

        root = Path(__file__).resolve().parents[2]

        application_id = (
            "application-" + uuid4().hex[:12]
        )

        workspace = (
            MANAGED_APPLICATION_ROOT
            / application_id
            / ("task-" + uuid4().hex)
        )

        workspace.mkdir(
            parents=True,
            exist_ok=False,
        )

        writer = DataEngineRecordWriter()
        workspace_id = register_managed_workspace(workspace)

        changed: set[str] = set()
        model_calls: list[dict[str, Any]] = []

        text = request.question.strip()

        # Select only the independent acceptance contract.
        # This does not select a model or application template.
        fitness = all(
            term in text.lower()
            for term in ("calori", "mile", "weight")
        )

        def record(kind: str, **data):
            self._record(
                writer,
                request.request_id,
                application_id,
                kind,
                data,
            )

        def progress(kind: str, **details):
            emit_event(
                kind,
                application_id=application_id,
                **details,
            )

        def ask(stage: str, prompt: str) -> str:
            progress(
                "model_step_started",
                stage=stage,
            )

            started = time.monotonic()

            result = process_automatic_model_request(
                question=prompt,
                required_capability="code_generation",
                request_id=request.request_id,
            )

            raw = result.get("raw") or {}

            if not isinstance(raw, dict):
                raw = {}

            metadata = raw.get("metadata") or {}

            if not isinstance(metadata, dict):
                metadata = {}

            answer = str(result.get("answer") or "")

            if not answer.strip():
                raise ValueError(
                    f"Model returned empty output: {stage}"
                )

            reason = metadata.get("done_reason")

            if reason is not None and reason != "stop":
                raise ValueError(
                    f"Model output incomplete: {stage}: {reason}"
                )

            details = {
                "stage": stage,
                "provider_id": raw.get("provider_id"),
                "model_id": raw.get("model_id"),
                "processing_location": raw.get(
                    "processing_location"
                ),
                "model_selection": raw.get("selection"),
                "output_sha256": hashlib.sha256(
                    answer.encode("utf-8")
                ).hexdigest(),
                "output_length": len(answer),
                "done_reason": reason,
                "generation_profile": metadata.get(
                    "generation_profile"
                ),
                "elapsed_seconds": round(
                    time.monotonic() - started,
                    2,
                ),
            }

            record("model_call", **details)
            model_calls.append(details)

            progress(
                "model_step_finished",
                stage=stage,
                model_id=raw.get("model_id"),
            )

            return answer

        def write(
            path: str,
            contents: str,
            plan_id: str,
        ):
            result = instance.execute_tool(
                "write_files",
                {
                    "workspace_id": workspace_id,
                    "files": [
                        {
                            "path": path,
                            "content": contents,
                        }
                    ],
                },
            )

            files = result.get("files", [])

            if (
                not isinstance(files, list)
                or not any(
                    item.get("path") == path
                    for item in files
                )
            ):
                raise RuntimeError(
                    f"File tool did not confirm write: {path}"
                )

            target = (
                workspace / path
            ).resolve(strict=True)

            if (
                not target.is_file()
                or not target.is_relative_to(workspace)
            ):
                raise RuntimeError(
                    f"Generated file unavailable: {path}"
                )

            digest = hashlib.sha256(
                target.read_bytes()
            ).hexdigest()

            expected = hashlib.sha256(
                contents.encode("utf-8")
            ).hexdigest()

            if digest != expected:
                raise RuntimeError(
                    f"File write/readback mismatch: {path}"
                )

            changed.add(path)

            record(
                "code_change",
                path=path,
                sha256=digest,
                plan_id=plan_id,
            )

            progress(
                "file_written",
                path=path,
                sha256=digest,
            )

        try:
            record(
                "application_generation_request",
                question=text,
                workspace=str(workspace),
            )

            progress("project_created")

            initial = instance.execute_tool(
                "list_files",
                {
                    "workspace_id": workspace_id,
                    "path": ".",
                    "recursive": True,
                },
            )

            if initial.get("count") != 0:
                raise RuntimeError(
                    "New managed workspace is not empty"
                )

            inspection = RepositoryInspection.create(
                requirement_id=request.request_id,
                repository_root=str(workspace),
                inspected_paths=(".",),
                findings=(
                    "workspace.initially_empty=true",
                ),
            )

            record(
                "project_inspection",
                **inspection.to_dict(),
            )

            acceptance_contract = (
                "For fitness acceptance, include tracker.py. "
                "It must export FitnessTracker(path) with methods "
                "add_activity(distance_miles, calories_burned, weight_lbs), "
                "history(), totals(), save(), and load(). "
                "totals() must return distance_miles and calories_burned. "
                "Reject invalid, negative, and non-finite values. "
                "save() must write a JSON array containing exactly "
                "source, category, data_type, value, and unit "
                "for each measurement. "
                if fitness
                else ""
            )

            rules = (
                "Use Python 3.12 standard library only. "
                "No network or package installations. "
                "main.py must run without arguments, demonstrate "
                "the requested functionality using a temporary "
                "directory, print its result, and exit successfully. "
                "Create unittest tests in tests/test_*.py that "
                "exercise real application behavior. "
                + acceptance_contract
            )

            manifest_prompt = (
                "Plan a functional Python application. "
                "Return ONLY one JSON object with application_name, "
                "summary, and files. "
                "files must contain 2 to 6 objects with path and purpose. "
                "Use .py files at the top level or tests/test_*.py. "
                "Include main.py and at least one test file. "
                "Do not include file contents in the manifest. "
                + rules
                + "\nUSER REQUEST:\n"
                + text
            )

            manifest = validate_manifest(
                clean_json(
                    ask("manifest", manifest_prompt)
                ),
                fitness=fitness,
            )

            record(
                "application_manifest",
                **manifest,
            )

            plan_files = list(manifest["files"])

            if fitness:
                plan_files.append({
                    "path": "tests/test_dataworc_acceptance.py",
                    "purpose": "Independent acceptance tests",
                })

            proposal = {
                **manifest,
                "files": plan_files,
            }

            plan = self._engineering_plan(
                proposal,
                inspection,
                request.request_id,
                set(),
            )

            engineering = ApplicationEngineeringRuntime(
                project_root=root,
                workspace=workspace,
                application_id=application_id,
                requirement_id=request.request_id,
                writer=writer,
            )

            engineering.validate_plan(
                plan=plan,
                inspection=inspection,
            )

            record(
                "engineering_plan",
                **plan.to_dict(),
            )

            # Install deterministic checks before model-generated code.
            for path, code in CHECK_FILES.items():
                write(
                    path,
                    code,
                    plan.plan_id,
                )

            if fitness:
                write(
                    "tests/test_dataworc_acceptance.py",
                    FITNESS_ACCEPTANCE,
                    plan.plan_id,
                )

            written: dict[str, str] = {}

            # Each file receives its own real local model call.
            for item in manifest["files"]:
                path = item["path"]

                relevant = "\n".join(
                    f"{name}:\n{source[:1200]}"
                    for name, source in list(written.items())[-2:]
                )[-2400:]

                role = (
                    "Entry point only: import the application and run a demo."
                    if path == "main.py" else
                    "Data model and persistence only."
                    if path == "tracker.py" else
                    "Unittest assertions only; import existing modules."
                    if path.startswith("tests/") else
                    item["purpose"]
                )

                contract = acceptance_contract if fitness else rules

                prompt = (
                    f"Generate ONLY complete Python 3.12 source for {path}. "
                    "No markdown, commentary, duplicated modules or long docstrings. "
                    "Keep the implementation concise; target under 1800 output tokens. "
                    f"Responsibility: {role}\n"
                    f"Required behavior: {text[:1800]}\n"
                    f"Contract: {contract[:1600]}\n"
                    "Planned paths: "
                    + ", ".join(f["path"] for f in manifest["files"])
                    + "\nRelevant existing code:\n" + relevant
                )

                for attempt in (1, 2):
                    try:
                        result = ask(f"file:{path}:attempt:{attempt}", prompt)
                        contents = clean_source(result, path)
                        compile(contents, path, "exec")
                        break
                    except Exception as error:
                        message = str(error).lower()
                        recoverable = (
                            "configured output limit" in message
                            or isinstance(error, SyntaxError)
                            or "incomplete generated source" in message
                        )
                        if attempt == 2 or not recoverable:
                            raise

                        record(
                            "generation_retry",
                            path=path,
                            attempt=attempt,
                            reason=str(error)[:240],
                        )

                        prompt += (
                            "\nRETRY: complete this ONE file using fewer "
                            "than 1200 output tokens. Reuse imports; "
                            "omit nonessential text; preserve behavior."
                        )

                write(
                    path,
                    contents,
                    plan.plan_id,
                )

                written[path] = contents

            progress(
                "validation_started",
                stage="engineering",
            )

            result = engineering.execute(
                plan=plan,
                inspection=inspection,
            )

            repairs = 0

            # Repair a failed real compile/test/run operation.
            while (
                not result["success"]
                and repairs < MAX_REPAIRS
            ):
                repairs += 1

                failure = (
                    result.get("failed_result") or {}
                )

                repair_prompt = (
                    "Fix the real engineering failure by rewriting "
                    "exactly one previously planned source file. "
                    "Return PATH: <file> on the first line, followed "
                    "by the complete corrected Python source. "
                    "Do not modify DataWorc engineering scripts or "
                    "tests/test_dataworc_acceptance.py. "
                    "\nFAILURE:\n"
                    + json.dumps(
                        failure,
                        default=str,
                    )[-4500:]
                    + "\nCURRENT FILES:\n"
                    + "\n".join(
                        f"### {name}\n{contents[:4000]}"
                        for name, contents in written.items()
                    )[-15000:]
                    + "\n"
                    + rules
                )

                response = ask(
                    "repair:" + str(repairs),
                    repair_prompt,
                )

                first, separator, rest = (
                    response.partition("\n")
                )

                if (
                    not separator
                    or not first.startswith("PATH: ")
                ):
                    raise ValueError(
                        "Repair must begin with PATH: <file>"
                    )

                repair_path = source_path(
                    first[6:].strip()
                )

                if repair_path not in written:
                    raise ValueError(
                        "Repair attempted unplanned file: "
                        + repair_path
                    )

                repaired = clean_source(
                    rest,
                    repair_path,
                )

                repair_inspection = (
                    RepositoryInspection.create(
                        requirement_id=request.request_id,
                        repository_root=str(workspace),
                        inspected_paths=tuple(
                            sorted(changed)
                        ),
                        findings=(
                            f"repair_attempt={repairs}",
                        ),
                    )
                )

                repair_plan = self._engineering_plan(
                    proposal,
                    repair_inspection,
                    request.request_id,
                    set(changed),
                )

                engineering.validate_plan(
                    plan=repair_plan,
                    inspection=repair_inspection,
                )

                write(
                    repair_path,
                    repaired,
                    repair_plan.plan_id,
                )

                record(
                    "repair_result",
                    attempt=repairs,
                    path=repair_path,
                    failure=failure,
                )

                written[repair_path] = repaired

                plan = repair_plan
                inspection = repair_inspection

                progress(
                    "validation_started",
                    stage="engineering",
                    repair_attempt=repairs,
                )

                result = engineering.execute(
                    plan=plan,
                    inspection=inspection,
                )

            progress(
                "validation_recorded",
                stage="engineering",
                success=result["success"],
            )

            if not result["success"]:
                record(
                    "application_generation_result",
                    status="failed",
                    engineering_result=result,
                )

                return {
                    "capability": self.name,
                    "source": "application_engineering",
                    "status": "error",
                    "answer": (
                        "Generated application failed "
                        "real engineering verification."
                    ),
                    "data": {
                        "application_id": application_id,
                        "workspace": str(workspace),
                        "engineering_result": result,
                        "repair_attempts": repairs,
                    },
                    "errors": [
                        "gVisor engineering checks failed"
                    ],
                }

            # Model-written tests are insufficient for a claim of
            # complete functionality without independent acceptance.
            if not fitness:
                record(
                    "application_generation_result",
                    status="needs_independent_acceptance",
                )

                return {
                    "capability": self.name,
                    "source": "application_engineering",
                    "status": "partial",
                    "answer": (
                        "Generated source passed sandbox checks, "
                        "but independent requirements acceptance "
                        "is still pending."
                    ),
                    "data": {
                        "application_id": application_id,
                        "workspace": str(workspace),
                        "engineering_result": result,
                        "files": sorted(changed),
                    },
                    "errors": [
                        "independent acceptance contract unavailable"
                    ],
                }

            checkpoint = (
                engineering.create_verified_checkpoint(
                    changed_paths=sorted(changed),
                    verification_passed=True,
                    plan_id=plan.plan_id,
                )
            )

            record(
                "application_generation_result",
                status="succeeded",
                workspace=str(workspace),
                engineering_result=result,
                checkpoint=checkpoint,
                files=sorted(changed),
            )

            return {
                "capability": self.name,
                "source": "application_engineering",
                "status": "success",
                "answer": (
                    "Fitness application generated and "
                    "independently tested in gVisor."
                ),
                "data": {
                    "status": "succeeded",
                    "application_id": application_id,
                    "workspace": str(workspace),
                    "application_name": manifest[
                        "application_name"
                    ],
                    "changed_paths": sorted(changed),
                    "engineering_result": result,
                    "checkpoint": checkpoint,
                    "model_calls": model_calls,
                    "repair_attempts": repairs,
                    "independent_acceptance": True,
                },
                "errors": [],
            }

        except Exception as error:
            try:
                record(
                    "application_generation_result",
                    status="error",
                    error=str(error),
                )
            except Exception:
                pass

            return {
                "capability": self.name,
                "source": self.name,
                "status": "error",
                "answer": (
                    "Application Generation could not "
                    "finish verification."
                ),
                "data": {
                    "application_id": application_id,
                    "workspace": str(workspace),
                    "error": str(error),
                    "model_calls": model_calls,
                },
                "errors": [str(error)],
            }

        finally:
            release_managed_workspace(workspace_id)
