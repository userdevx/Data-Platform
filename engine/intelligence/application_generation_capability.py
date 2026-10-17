from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.application.automatic_model_request_action import (
    process_automatic_model_request,
)
from engine.application_engineering.models import (
    EngineeringPlan,
    PlannedFileChange,
    RepositoryInspection,
    ValidationStep,
)
from engine.application_engineering.runtime import (
    ApplicationEngineeringRuntime,
)
from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.tools.file_tools import (
    MANAGED_APPLICATION_ROOT,
    register_managed_workspace,
    release_managed_workspace,
)


class ApplicationGenerationCapability:
    name = "application_generation"

    MAX_REPAIRS = 3

    @staticmethod
    def _parse_json_object(
        text: str,
    ) -> dict[str, Any]:
        cleaned = text.strip()

        if not cleaned:
            raise ValueError(
                "Code-generation model "
                "returned no output."
            )

        if (
            cleaned.startswith(
                "```"
            )
            or cleaned.endswith(
                "```"
            )
        ):
            raise ValueError(
                "Code-generation model "
                "returned markdown instead "
                "of the required JSON object."
            )

        try:
            value = json.loads(
                cleaned
            )
        except json.JSONDecodeError as error:
            # Carry the model's actual output. A parse failure with
            # no sample is unrepairable.
            raise ValueError(
                "Code-generation model "
                "did not return valid JSON. "
                f"Received: {cleaned[:400]!r}"
            ) from error

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                "Code-generation result "
                "must be a JSON object."
            )

        return value

    @staticmethod
    def _validate_proposal(
        proposal: dict[str, Any],
    ) -> None:
        files = proposal.get(
            "files"
        )

        validation_steps = (
            proposal.get(
                "validation_steps"
            )
        )

        if (
            not isinstance(
                proposal.get(
                    "application_name"
                ),
                str,
            )
            or not proposal[
                "application_name"
            ].strip()
        ):
            raise ValueError(
                "Generated proposal requires "
                "application_name."
            )

        if (
            not isinstance(
                proposal.get(
                    "summary"
                ),
                str,
            )
            or not proposal[
                "summary"
            ].strip()
        ):
            raise ValueError(
                "Generated proposal requires "
                "summary."
            )

        if (
            not isinstance(
                files,
                list,
            )
            or not files
        ):
            raise ValueError(
                "Generated proposal requires "
                "at least one complete file."
            )

        if len(files) > 32:
            raise ValueError(
                "Generated proposal contains "
                "too many files."
            )

        paths: set[str] = set()

        for file in files:
            if not isinstance(
                file,
                dict,
            ):
                raise ValueError(
                    "Generated file entry "
                    "must be an object."
                )

            path = file.get(
                "path"
            )

            purpose = file.get(
                "purpose"
            )

            content = file.get(
                "content"
            )

            if (
                not isinstance(
                    path,
                    str,
                )
                or not path.strip()
            ):
                raise ValueError(
                    "Generated file requires "
                    "a relative path."
                )

            if Path(path).is_absolute():
                raise ValueError(
                    "Generated file path "
                    "cannot be absolute."
                )

            if ".." in Path(
                path
            ).parts:
                raise ValueError(
                    "Generated file path "
                    "cannot escape workspace."
                )

            if (
                ".git"
                in Path(path).parts
            ):
                raise ValueError(
                    "Generated source cannot "
                    "write Git internals."
                )

            if (
                Path(path).name
                == ".env"
                or Path(path).name.startswith(
                    ".env."
                )
            ):
                raise ValueError(
                    "Generated source cannot "
                    "write credential files."
                )

            if path in paths:
                raise ValueError(
                    "Generated proposal contains "
                    "duplicate file paths."
                )

            paths.add(path)

            if not isinstance(
                content,
                str,
            ):
                raise ValueError(
                    "Generated files require "
                    "complete text content."
                )

            if (
                not isinstance(
                    purpose,
                    str,
                )
                or not purpose.strip()
            ):
                raise ValueError(
                    "Generated files require "
                    "a purpose."
                )

        if (
            not isinstance(
                validation_steps,
                list,
            )
            or not validation_steps
        ):
            raise ValueError(
                "Generated proposal requires "
                "validation steps."
            )

        stages: set[str] = set()

        for step in (
            validation_steps
        ):
            if not isinstance(
                step,
                dict,
            ):
                raise ValueError(
                    "Validation step must "
                    "be an object."
                )

            description = (
                step.get(
                    "description"
                )
            )

            command = step.get(
                "command"
            )

            if (
                not isinstance(
                    description,
                    str,
                )
                or ":" not in description
            ):
                raise ValueError(
                    "Validation descriptions "
                    "must begin with a "
                    "lifecycle stage."
                )

            stage = (
                description
                .split(
                    ":",
                    1,
                )[0]
                .strip()
                .lower()
            )

            if stage not in {
                "compile",
                "test",
                "build",
                "run",
            }:
                raise ValueError(
                    "Invalid validation stage: "
                    + stage
                )

            stages.add(stage)

            if (
                not isinstance(
                    command,
                    str,
                )
                or not command.strip()
            ):
                raise ValueError(
                    "Validation step requires "
                    "an approved command."
                )

        if "test" not in stages:
            raise ValueError(
                "Generated application requires "
                "a test stage."
            )

        if "run" not in stages:
            raise ValueError(
                "Generated application requires "
                "a runtime verification stage."
            )

    @staticmethod
    def _proposal_prompt(
        request_text: str,
    ) -> str:
        return (
            "Produce the complete software application "
            "requested below.\n"
            "Return ONLY one valid JSON object and no "
            "markdown or prose outside the JSON.\n\n"
            "The JSON object must contain:\n"
            'application_name: non-empty string\n'
            'summary: non-empty string\n'
            'files: array of objects containing path, '
            'purpose, and complete content\n'
            'validation_steps: array of objects containing '
            'description and command\n'
            'risks: array of strings\n\n'
            "All file paths must be relative to the managed "
            "application workspace. Do not assume any starter "
            "files exist. Do not write .git or credential "
            "environment files. Do not require dependency "
            "installation during validation. Prefer locally "
            "available built-in/runtime functionality when "
            "the requirement permits it.\n\n"
            "Every validation description must begin with "
            "compile:, test:, build:, or run:. A test stage "
            "and run stage are mandatory. The test stage must "
            "exercise the actual requested behavior. The run "
            "stage must execute the actual application. "
            "Commands must be direct commands, not shell "
            "pipelines or compound shell expressions.\n\n"
            "SYSTEM REQUEST:\n"
            + request_text
        )

    @staticmethod
    def _repair_prompt(
        *,
        request_text: str,
        failure: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> str:
        return (
            "Repair the generated application after a real "
            "Application Engineering failure.\n"
            "Return ONLY one valid JSON object with the same "
            "schema as the original generation request: "
            "application_name, summary, files, "
            "validation_steps, risks.\n"
            "Every file entry must contain the COMPLETE "
            "replacement file content. Do not return partial excerpts.\n\n"
            "SYSTEM REQUEST:\n"
            + request_text
            + "\n\nREAL ENGINEERING FAILURE:\n"
            + json.dumps(
                failure,
                sort_keys=True,
            )
            + "\n\nCOMPLETE CURRENT FILES:\n"
            + json.dumps(
                files,
                sort_keys=True,
            )
        )

    @staticmethod
    def _plan_from_proposal(
        *,
        proposal: dict[str, Any],
        inspection: RepositoryInspection,
        requirement_id: str,
        existing_paths: set[str],
    ) -> EngineeringPlan:
        planned_changes = tuple(
            PlannedFileChange(
                path=str(
                    item["path"]
                ),
                operation=(
                    "modify"
                    if (
                        str(
                            item["path"]
                        )
                        in existing_paths
                    )
                    else "create"
                ),
                purpose=str(
                    item["purpose"]
                ),
            )
            for item
            in proposal["files"]
        )

        validation_steps = tuple(
            ValidationStep(
                description=str(
                    item[
                        "description"
                    ]
                ),
                command=str(
                    item[
                        "command"
                    ]
                ),
            )
            for item
            in proposal[
                "validation_steps"
            ]
        )

        risks_raw = proposal.get(
            "risks",
            [],
        )

        risks = tuple(
            str(item)
            for item
            in risks_raw
            if str(item).strip()
        )

        return EngineeringPlan.create(
            requirement_id=(
                requirement_id
            ),
            inspection_id=(
                inspection.inspection_id
            ),
            summary=str(
                proposal["summary"]
            ),
            planned_changes=(
                planned_changes
            ),
            validation_steps=(
                validation_steps
            ),
            risks=risks,
        )

    @staticmethod
    def _write_record(
        writer: DataEngineRecordWriter,
        *,
        data_type: str,
        request_id: str,
        application_id: str,
        value: dict[str, Any],
    ) -> None:
        writer.write(
            source=(
                "application_generation"
            ),
            category=(
                "application_generation"
            ),
            data_type=data_type,
            value={
                "request_id": (
                    request_id
                ),
                "application_id": (
                    application_id
                ),
                **value,
            },
            unit="record",
        )

    def execute(
        self,
        request,
        instance,
    ) -> dict:
        if not (
            instance.definition
            .permissions
            .write_records
        ):
            return {
                "capability": self.name,
                "source": (
                    "application_generation"
                ),
                "status": "rejected",
                "answer": (
                    "Application Generation "
                    "requires Data Engine "
                    "write permission."
                ),
                "data": {},
                "errors": [
                    "write_records is false"
                ],
            }

        if not (
            instance.definition
            .permissions
            .run_approved_commands
        ):
            return {
                "capability": self.name,
                "source": (
                    "application_generation"
                ),
                "status": "rejected",
                "answer": (
                    "Application Generation "
                    "requires approved command "
                    "execution."
                ),
                "data": {},
                "errors": [
                    "run_approved_commands "
                    "is false"
                ],
            }

        project_root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

        application_id = (
            "application-"
            + uuid4().hex[:12]
        )

        workspace = (
            MANAGED_APPLICATION_ROOT
            / application_id
            / (
                "task-"
                + uuid4().hex
            )
        )

        workspace.mkdir(
            parents=True,
            exist_ok=False,
        )

        writer = (
            DataEngineRecordWriter()
        )

        workspace_id = (
            register_managed_workspace(
                workspace
            )
        )

        changed_paths: set[str] = (
            set()
        )

        try:
            self._write_record(
                writer,
                data_type=(
                    "application_generation_request"
                ),
                request_id=(
                    request.request_id
                ),
                application_id=(
                    application_id
                ),
                value={
                    "question": (
                        request.question
                    ),
                    "route": (
                        "application_generation"
                    ),
                    "workspace": str(
                        workspace
                    ),
                },
            )

            initial_list = (
                instance.execute_tool(
                    "list_files",
                    {
                        "workspace_id": (
                            workspace_id
                        ),
                        "path": ".",
                        "recursive": True,
                    },
                )
            )

            if (
                initial_list.get(
                    "count"
                )
                != 0
            ):
                raise RuntimeError(
                    "New application workspace "
                    "was not empty."
                )

            inspection = (
                RepositoryInspection.create(
                    requirement_id=(
                        request.request_id
                    ),
                    repository_root=str(
                        workspace
                    ),
                    inspected_paths=(
                        ".",
                    ),
                    findings=(
                        "workspace.initially_empty=true",
                    ),
                )
            )

            self._write_record(
                writer,
                data_type=(
                    "project_inspection"
                ),
                request_id=(
                    request.request_id
                ),
                application_id=(
                    application_id
                ),
                value=(
                    inspection.to_dict()
                ),
            )

            model_result = (
                process_automatic_model_request(
                    question=(
                        self._proposal_prompt(
                            request.question
                        )
                    ),
                    required_capability=(
                        "code_generation"
                    ),
                    request_id=(
                        request.request_id
                    ),
                )
            )

            raw = model_result.get(
                "raw",
                {},
            )

            if not isinstance(
                raw,
                dict,
            ):
                raw = {}

            selection = raw.get(
                "selection",
                {},
            )

            if not isinstance(
                selection,
                dict,
            ):
                selection = {}

            self._write_record(
                writer,
                data_type=(
                    "model_selection"
                ),
                request_id=(
                    request.request_id
                ),
                application_id=(
                    application_id
                ),
                value={
                    "required_capability": (
                        "code_generation"
                    ),
                    "selection": (
                        selection
                    ),
                    "provider_id": (
                        raw.get(
                            "provider_id"
                        )
                    ),
                    "model_id": (
                        raw.get(
                            "model_id"
                        )
                    ),
                },
            )

            proposal = (
                self._parse_json_object(
                    str(
                        model_result.get(
                            "answer",
                            "",
                        )
                    )
                )
            )

            self._validate_proposal(
                proposal
            )

            current_paths: set[str] = (
                set()
            )

            plan = (
                self._plan_from_proposal(
                    proposal=proposal,
                    inspection=inspection,
                    requirement_id=(
                        request.request_id
                    ),
                    existing_paths=(
                        current_paths
                    ),
                )
            )

            engineering = (
                ApplicationEngineeringRuntime(
                    project_root=(
                        project_root
                    ),
                    workspace=workspace,
                    application_id=(
                        application_id
                    ),
                    requirement_id=(
                        request.request_id
                    ),
                    writer=writer,
                )
            )

            engineering.validate_plan(
                plan=plan,
                inspection=inspection,
            )

            self._write_record(
                writer,
                data_type=(
                    "engineering_plan"
                ),
                request_id=(
                    request.request_id
                ),
                application_id=(
                    application_id
                ),
                value=(
                    plan.to_dict()
                ),
            )

            write_result = (
                instance.execute_tool(
                    "write_files",
                    {
                        "workspace_id": (
                            workspace_id
                        ),
                        "files": [
                            {
                                "path": str(
                                    item[
                                        "path"
                                    ]
                                ),
                                "content": str(
                                    item[
                                        "content"
                                    ]
                                ),
                            }
                            for item
                            in proposal[
                                "files"
                            ]
                        ],
                    },
                )
            )

            for item in (
                write_result.get(
                    "files",
                    []
                )
            ):
                path = str(
                    item.get(
                        "path",
                        "",
                    )
                )

                if (
                    path
                    and item.get(
                        "changed"
                    )
                ):
                    changed_paths.add(
                        path
                    )

                self._write_record(
                    writer,
                    data_type=(
                        "code_change"
                    ),
                    request_id=(
                        request.request_id
                    ),
                    application_id=(
                        application_id
                    ),
                    value={
                        "plan_id": (
                            plan.plan_id
                        ),
                        **item,
                    },
                )

            generated_paths = sorted(
                changed_paths
            )

            for start in range(
                0,
                len(
                    generated_paths
                ),
                16,
            ):
                read_result = (
                    instance.execute_tool(
                        "read_files",
                        {
                            "workspace_id": (
                                workspace_id
                            ),
                            "paths": (
                                generated_paths[
                                    start:
                                    start + 16
                                ]
                            ),
                        },
                    )
                )

                self._write_record(
                    writer,
                    data_type=(
                        "tool_execution"
                    ),
                    request_id=(
                        request.request_id
                    ),
                    application_id=(
                        application_id
                    ),
                    value={
                        "tool": (
                            "read_files"
                        ),
                        "file_count": (
                            read_result.get(
                                "file_count",
                                0,
                            )
                        ),
                        "files": [
                            {
                                "path": (
                                    item.get(
                                        "path"
                                    )
                                ),
                                "bytes": (
                                    item.get(
                                        "bytes"
                                    )
                                ),
                                "sha256": (
                                    item.get(
                                        "sha256"
                                    )
                                ),
                            }
                            for item
                            in read_result.get(
                                "files",
                                [],
                            )
                        ],
                    },
                )

            engineering_result = (
                engineering.execute(
                    plan=plan,
                    inspection=inspection,
                )
            )

            repairs = 0

            while (
                not engineering_result[
                    "success"
                ]
                and repairs
                < self.MAX_REPAIRS
            ):
                repairs += 1

                list_result = (
                    instance.execute_tool(
                        "list_files",
                        {
                            "workspace_id": (
                                workspace_id
                            ),
                            "path": ".",
                            "recursive": True,
                        },
                    )
                )

                current_paths = {
                    str(
                        item["path"]
                    )
                    for item
                    in list_result.get(
                        "entries",
                        [],
                    )
                    if (
                        item.get(
                            "type"
                        )
                        == "file"
                    )
                }

                complete_files: list[
                    dict[str, Any]
                ] = []

                ordered_paths = sorted(
                    current_paths
                )

                for start in range(
                    0,
                    len(
                        ordered_paths
                    ),
                    16,
                ):
                    batch = (
                        instance.execute_tool(
                            "read_files",
                            {
                                "workspace_id": (
                                    workspace_id
                                ),
                                "paths": (
                                    ordered_paths[
                                        start:
                                        start + 16
                                    ]
                                ),
                            },
                        )
                    )

                    complete_files.extend(
                        batch.get(
                            "files",
                            [],
                        )
                    )

                repair_model_result = (
                    process_automatic_model_request(
                        question=(
                            self._repair_prompt(
                                request_text=(
                                    request.question
                                ),
                                failure=(
                                    engineering_result
                                ),
                                files=(
                                    complete_files
                                ),
                            )
                        ),
                        required_capability=(
                            "code_generation"
                        ),
                        request_id=(
                            request.request_id
                        ),
                    )
                )

                repair_proposal = (
                    self._parse_json_object(
                        str(
                            repair_model_result.get(
                                "answer",
                                "",
                            )
                        )
                    )
                )

                self._validate_proposal(
                    repair_proposal
                )

                repair_inspection = (
                    RepositoryInspection.create(
                        requirement_id=(
                            request.request_id
                        ),
                        repository_root=str(
                            workspace
                        ),
                        inspected_paths=(
                            tuple(
                                ordered_paths
                            )
                            if ordered_paths
                            else (
                                ".",
                            )
                        ),
                        findings=(
                            (
                                "repair_attempt="
                                + str(
                                    repairs
                                )
                            ),
                        ),
                    )
                )

                repair_plan = (
                    self._plan_from_proposal(
                        proposal=(
                            repair_proposal
                        ),
                        inspection=(
                            repair_inspection
                        ),
                        requirement_id=(
                            request.request_id
                        ),
                        existing_paths=(
                            current_paths
                        ),
                    )
                )

                engineering.validate_plan(
                    plan=repair_plan,
                    inspection=(
                        repair_inspection
                    ),
                )

                self._write_record(
                    writer,
                    data_type=(
                        "repair_result"
                    ),
                    request_id=(
                        request.request_id
                    ),
                    application_id=(
                        application_id
                    ),
                    value={
                        "repair_attempt": (
                            repairs
                        ),
                        "previous_failure": (
                            engineering_result
                        ),
                        "repair_plan": (
                            repair_plan.to_dict()
                        ),
                    },
                )

                repair_write = (
                    instance.execute_tool(
                        "write_files",
                        {
                            "workspace_id": (
                                workspace_id
                            ),
                            "files": [
                                {
                                    "path": str(
                                        item[
                                            "path"
                                        ]
                                    ),
                                    "content": str(
                                        item[
                                            "content"
                                        ]
                                    ),
                                }
                                for item
                                in repair_proposal[
                                    "files"
                                ]
                            ],
                        },
                    )
                )

                for item in (
                    repair_write.get(
                        "files",
                        []
                    )
                ):
                    if item.get(
                        "changed"
                    ):
                        changed_paths.add(
                            str(
                                item[
                                    "path"
                                ]
                            )
                        )

                repair_paths = sorted(
                    {
                        str(
                            item[
                                "path"
                            ]
                        )
                        for item
                        in repair_proposal[
                            "files"
                        ]
                    }
                )

                for start in range(
                    0,
                    len(
                        repair_paths
                    ),
                    16,
                ):
                    instance.execute_tool(
                        "read_files",
                        {
                            "workspace_id": (
                                workspace_id
                            ),
                            "paths": (
                                repair_paths[
                                    start:
                                    start + 16
                                ]
                            ),
                        },
                    )

                plan = repair_plan
                inspection = (
                    repair_inspection
                )

                engineering_result = (
                    engineering.execute(
                        plan=plan,
                        inspection=inspection,
                    )
                )

            if not engineering_result[
                "success"
            ]:
                self._write_record(
                    writer,
                    data_type=(
                        "application_generation_result"
                    ),
                    request_id=(
                        request.request_id
                    ),
                    application_id=(
                        application_id
                    ),
                    value={
                        "status": "failed",
                        "workspace": str(
                            workspace
                        ),
                        "repairs": repairs,
                        "engineering_result": (
                            engineering_result
                        ),
                    },
                )

                return {
                    "capability": self.name,
                    "source": (
                        "application_engineering"
                    ),
                    "status": "error",
                    "answer": (
                        "Application Generation "
                        "did not pass the required "
                        "engineering verification."
                    ),
                    "data": {
                        "application_id": (
                            application_id
                        ),
                        "workspace": str(
                            workspace
                        ),
                        "repair_attempts": (
                            repairs
                        ),
                        "engineering_result": (
                            engineering_result
                        ),
                    },
                    "errors": [
                        "engineering verification "
                        "failed"
                    ],
                }

            checkpoint = (
                engineering
                .create_verified_checkpoint(
                    changed_paths=(
                        sorted(
                            changed_paths
                        )
                    ),
                    verification_passed=True,
                    plan_id=(
                        plan.plan_id
                    ),
                )
            )

            final_value = {
                "status": "succeeded",
                "workspace": str(
                    workspace
                ),
                "application_name": (
                    proposal.get(
                        "application_name"
                    )
                ),
                "changed_paths": sorted(
                    changed_paths
                ),
                "repair_attempts": (
                    repairs
                ),
                "engineering_result": (
                    engineering_result
                ),
                "checkpoint": (
                    checkpoint
                ),
                "model_selection": (
                    selection
                ),
            }

            self._write_record(
                writer,
                data_type=(
                    "application_generation_result"
                ),
                request_id=(
                    request.request_id
                ),
                application_id=(
                    application_id
                ),
                value=final_value,
            )

            return {
                "capability": self.name,
                "source": (
                    "application_engineering"
                ),
                "status": "success",
                "answer": (
                    "The software application "
                    "was generated, verified, "
                    "and checkpointed."
                ),
                "data": {
                    "action": (
                        "Generated and verified "
                        "software."
                    ),
                    "explanation": (
                        "The Intelligence Runtime "
                        "routed the request to "
                        "Application Generation. "
                        "Application Engineering "
                        "planned, generated, tested, "
                        "ran, repaired when needed, "
                        "and checkpointed the "
                        "verified result."
                    ),
                    "next_step": (
                        "Inspect or release the "
                        "verified application."
                    ),
                    "application_id": (
                        application_id
                    ),
                    **final_value,
                },
                "errors": [],
            }

        except Exception as error:
            try:
                self._write_record(
                    writer,
                    data_type=(
                        "application_generation_result"
                    ),
                    request_id=(
                        request.request_id
                    ),
                    application_id=(
                        application_id
                    ),
                    value={
                        "status": "error",
                        "workspace": str(
                            workspace
                        ),
                        "error": str(
                            error
                        ),
                    },
                )
            except Exception:
                pass

            return {
                "capability": self.name,
                "source": (
                    "application_generation"
                ),
                "status": "error",
                "answer": (
                    "Application Generation "
                    "could not complete the "
                    "engineering lifecycle."
                ),
                "data": {
                    "application_id": (
                        application_id
                    ),
                    "workspace": str(
                        workspace
                    ),
                    "error": str(
                        error
                    ),
                },
                "errors": [
                    str(error)
                ],
            }

        finally:
            release_managed_workspace(
                workspace_id
            )
