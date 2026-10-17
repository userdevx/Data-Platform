from __future__ import annotations

import json
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Any

from engine.application_engineering.models import (
    EngineeringPlan,
    RepositoryInspection,
    ValidationStep,
)
from engine.application_engineering.validation import (
    EngineeringPlanValidator,
)
from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)


_STAGE_DATA_TYPES = {
    "compile": "compile_result",
    "test": "test_result",
    "build": "build_result",
    "run": "runtime_verification",
}


class ApplicationEngineeringError(
    RuntimeError
):
    pass


class ApplicationEngineeringRuntime:
    def __init__(
        self,
        *,
        project_root: Path,
        workspace: Path,
        application_id: str,
        requirement_id: str,
        writer: DataEngineRecordWriter,
    ) -> None:
        self.project_root = (
            project_root.resolve()
        )
        self.workspace = (
            workspace.resolve()
        )
        self.application_id = (
            application_id
        )
        self.requirement_id = (
            requirement_id
        )
        self.writer = writer

    def _record(
        self,
        data_type: str,
        value: dict[str, Any],
    ) -> None:
        self.writer.write(
            source=(
                "application_engineering"
            ),
            category=(
                "application_engineering"
            ),
            data_type=data_type,
            value={
                "application_id": (
                    self.application_id
                ),
                "requirement_id": (
                    self.requirement_id
                ),
                **value,
            },
            unit="record",
        )

    @staticmethod
    def _stage(
        step: ValidationStep,
    ) -> str:
        description = (
            step.description
            .strip()
            .lower()
        )

        if ":" not in description:
            raise ApplicationEngineeringError(
                "Validation descriptions "
                "must begin with a lifecycle "
                "stage followed by ':'."
            )

        stage = (
            description
            .split(
                ":",
                1,
            )[0]
            .strip()
        )

        if (
            stage
            not in _STAGE_DATA_TYPES
        ):
            raise ApplicationEngineeringError(
                "Unknown engineering stage: "
                + stage
            )

        return stage

    def validate_plan(
        self,
        *,
        plan: EngineeringPlan,
        inspection: RepositoryInspection,
    ) -> None:
        result = (
            EngineeringPlanValidator()
            .validate(
                plan=plan,
                inspection=inspection,
                requirement_id=(
                    self.requirement_id
                ),
            )
        )

        if not result.valid:
            raise ApplicationEngineeringError(
                "Engineering Plan rejected: "
                + ", ".join(
                    result.reasons
                )
            )

        stages = [
            self._stage(step)
            for step
            in plan.validation_steps
        ]

        if "test" not in stages:
            raise ApplicationEngineeringError(
                "Engineering Plan requires "
                "a test stage."
            )

        if "run" not in stages:
            raise ApplicationEngineeringError(
                "Engineering Plan requires "
                "a real runtime stage."
            )

        self._record(
            "engineering_plan_validation",
            {
                "plan_id": (
                    plan.plan_id
                ),
                "valid": True,
                "validation_stages": (
                    stages
                ),
            },
        )

    def _approved_command(
        self,
        command_text: str,
    ) -> list[str]:
        try:
            argv = shlex.split(
                command_text
            )
        except ValueError as error:
            raise ApplicationEngineeringError(
                "Invalid engineering command."
            ) from error

        if not argv:
            raise ApplicationEngineeringError(
                "Engineering command is empty."
            )

        blocked_tokens = {
            "&&",
            "||",
            "|",
            ">",
            ">>",
            "<",
            ";",
        }

        if any(
            token in blocked_tokens
            for token in argv
        ):
            raise ApplicationEngineeringError(
                "Shell composition is not allowed."
            )

        executable = argv[0]

        project_python = (
            self.project_root
            / "venv"
            / "bin"
            / "python"
        )

        if executable in {
            "python",
            "python3",
        }:
            if not project_python.is_file():
                raise ApplicationEngineeringError(
                    "Data Platform Python "
                    "runtime is unavailable."
                )

            argv[0] = str(
                project_python
            )

            return argv

        approved_names = {
            "node",
            "npm",
            "npx",
            "cargo",
            "rustc",
            "go",
            "gcc",
            "g++",
            "make",
            "cmake",
            "java",
            "javac",
        }

        if (
            executable
            not in approved_names
        ):
            raise ApplicationEngineeringError(
                "Executable is not approved: "
                + executable
            )

        resolved = shutil.which(
            executable
        )

        if resolved is None:
            raise ApplicationEngineeringError(
                "Required executable is "
                "not installed: "
                + executable
            )

        # Dependency installation is not part
        # of an automatically generated
        # validation command.
        if (
            executable == "npm"
            and len(argv) > 1
            and argv[1].lower()
            in {
                "install",
                "i",
                "add",
            }
        ):
            raise ApplicationEngineeringError(
                "Automatic dependency "
                "installation is blocked."
            )

        argv[0] = resolved

        return argv

    def _execute_step(
        self,
        step: ValidationStep,
    ) -> dict[str, Any]:
        stage = self._stage(
            step
        )

        if not step.command:
            raise ApplicationEngineeringError(
                "Every production validation "
                "step requires a command."
            )

        argv = self._approved_command(
            step.command
        )

        timeout = {
            "compile": 300,
            "test": 600,
            "build": 900,
            "run": 120,
        }[stage]

        try:
            completed = subprocess.run(
                argv,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            result = {
                "stage": stage,
                "description": (
                    step.description
                ),
                "argv": argv,
                "exit_code": (
                    completed.returncode
                ),
                "stdout": (
                    completed.stdout[
                        -12000:
                    ]
                ),
                "stderr": (
                    completed.stderr[
                        -12000:
                    ]
                ),
                "success": (
                    completed.returncode
                    == 0
                ),
            }

        except subprocess.TimeoutExpired:
            result = {
                "stage": stage,
                "description": (
                    step.description
                ),
                "argv": argv,
                "exit_code": -1,
                "stdout": "",
                "stderr": (
                    "Engineering command timed out."
                ),
                "success": False,
            }

        self._record(
            _STAGE_DATA_TYPES[
                stage
            ],
            result,
        )

        return result

    def execute(
        self,
        *,
        plan: EngineeringPlan,
        inspection: RepositoryInspection,
    ) -> dict[str, Any]:
        self.validate_plan(
            plan=plan,
            inspection=inspection,
        )

        stage_results = {
            "compile": [],
            "test": [],
            "build": [],
            "run": [],
        }

        for step in (
            plan.validation_steps
        ):
            result = (
                self._execute_step(
                    step
                )
            )

            stage_results[
                result["stage"]
            ].append(
                result
            )

            if not result[
                "success"
            ]:
                return {
                    "success": False,
                    "failed_stage": (
                        result["stage"]
                    ),
                    "failed_result": (
                        result
                    ),
                    "stages": (
                        stage_results
                    ),
                }

        return {
            "success": True,
            "failed_stage": None,
            "stages": stage_results,
        }

    def create_verified_checkpoint(
        self,
        *,
        changed_paths: list[str],
        verification_passed: bool,
        plan_id: str,
    ) -> dict[str, Any]:
        if not verification_passed:
            raise ApplicationEngineeringError(
                "A Git checkpoint cannot be "
                "created before verification."
            )

        normalized_paths = sorted(
            {
                str(
                    Path(path)
                )
                for path
                in changed_paths
                if str(path).strip()
            }
        )

        if not normalized_paths:
            raise ApplicationEngineeringError(
                "No verified changed paths "
                "were supplied."
            )

        git_dir = (
            self.workspace
            / ".git"
        )

        if not git_dir.exists():
            init_result = subprocess.run(
                [
                    "git",
                    "init",
                    "-b",
                    "main",
                ],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                check=False,
            )

            if (
                init_result.returncode
                != 0
            ):
                raise ApplicationEngineeringError(
                    "Git initialization failed: "
                    + init_result.stderr.strip()
                )

        name_result = subprocess.run(
            [
                "git",
                "config",
                "user.name",
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        email_result = subprocess.run(
            [
                "git",
                "config",
                "user.email",
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        if (
            not name_result.stdout.strip()
            or not email_result.stdout.strip()
        ):
            raise ApplicationEngineeringError(
                "Git user.name and user.email "
                "must already be configured."
            )

        stage_result = subprocess.run(
            [
                "git",
                "add",
                "--",
                *normalized_paths,
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        if (
            stage_result.returncode
            != 0
        ):
            raise ApplicationEngineeringError(
                "Selective Git staging failed."
            )

        names_result = subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--name-only",
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        staged_paths = sorted(
            line.strip()
            for line
            in names_result.stdout.splitlines()
            if line.strip()
        )

        if (
            staged_paths
            != normalized_paths
        ):
            raise ApplicationEngineeringError(
                "Staged paths do not match "
                "verified generated paths."
            )

        diff_check = subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--check",
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        if (
            diff_check.returncode
            != 0
        ):
            raise ApplicationEngineeringError(
                "Verified candidate diff "
                "failed git diff --check."
            )

        commit_result = subprocess.run(
            [
                "git",
                "commit",
                "-m",
                (
                    "Verified application "
                    "generation output"
                ),
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        if (
            commit_result.returncode
            != 0
        ):
            raise ApplicationEngineeringError(
                "Verified candidate commit failed: "
                + (
                    commit_result.stderr.strip()
                    or commit_result.stdout.strip()
                )
            )

        revision_result = (
            subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                check=True,
            )
        )

        revision = (
            revision_result.stdout.strip()
        )

        push_status = (
            "not_configured"
        )

        remote_result = subprocess.run(
            [
                "git",
                "remote",
                "get-url",
                "origin",
            ],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

        if (
            remote_result.returncode
            == 0
            and remote_result.stdout.strip()
        ):
            branch_result = subprocess.run(
                [
                    "git",
                    "branch",
                    "--show-current",
                ],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                check=False,
            )

            branch = (
                branch_result.stdout.strip()
                or "main"
            )

            push_result = subprocess.run(
                [
                    "git",
                    "push",
                    "-u",
                    "origin",
                    branch,
                ],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )

            push_status = (
                "pushed"
                if (
                    push_result.returncode
                    == 0
                )
                else "failed"
            )

        result = {
            "plan_id": plan_id,
            "revision": revision,
            "staged_paths": (
                staged_paths
            ),
            "diff_check_passed": True,
            "push_status": push_status,
            "verified_before_checkpoint": (
                True
            ),
        }

        self._record(
            "engineering_checkpoint",
            result,
        )

        return result
