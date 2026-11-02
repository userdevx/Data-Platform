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


from uuid import uuid4

from engine.application_engineering.execution_policy import (
    BuilderExecutionPolicy,
    make_builder_manager,
)
from engine.sandbox.models import (
    SandboxRequest,
    ResourceLimits,
    RuntimeKind,
    IsolationClass,
    TrustLevel,
    WorkloadType,
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
        execution_policy: BuilderExecutionPolicy | None = None,
        sandbox_manager: Any | None = None,
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
        self.execution_policy = (
            execution_policy
            if execution_policy is not None
            else BuilderExecutionPolicy.load(self.project_root)
        )
        self.sandbox_manager = (
            sandbox_manager
            if sandbox_manager is not None
            else make_builder_manager(self.execution_policy.image_id)
        )

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

    def _approved_command(self, command_text: str) -> list[str]:
        try:
            argv = shlex.split(command_text)
        except ValueError as exc:
            raise ApplicationEngineeringError(
                "Invalid engineering command."
            ) from exc

        if len(argv) != 2:
            raise ApplicationEngineeringError(
                "Only Python script execution is verified."
            )

        if argv[0] not in {"python", "python3"}:
            raise ApplicationEngineeringError(
                "Executable is not verified in the Builder image."
            )

        script_argument = argv[1]
        script_path = Path(script_argument)

        if (
            script_path.is_absolute()
            or not script_argument.endswith(".py")
            or script_argument.startswith("-")
            or any(part == ".." for part in script_path.parts)
        ):
            raise ApplicationEngineeringError(
                "Invalid Python script path."
            )

        resolved = (self.workspace / script_path).resolve()

        if (
            not resolved.is_relative_to(self.workspace)
            or not resolved.is_file()
        ):
            raise ApplicationEngineeringError(
                "Python script is outside the workspace or missing."
            )

        guest_path = (
            Path("/workspace")
            / resolved.relative_to(self.workspace)
        )
        return ["python3", str(guest_path)]

    def _execute_step(
        self,
        step: ValidationStep,
    ) -> dict[str, Any]:
        stage = self._stage(step)
        execution_id = str(uuid4())

        result: dict[str, Any] = {
            "stage": stage,
            "description": step.description,
            "argv": [],
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "success": False,
            "execution_id": execution_id,
            "runtime_kind": None,
            "isolation_class": None,
            "timed_out": False,
            "duration_seconds": None,
            "image_id": self.execution_policy.image_id,
        }

        try:
            if not step.command:
                raise ApplicationEngineeringError(
                    "Engineering validation command is missing."
                )

            argv = self._approved_command(step.command)
            result["argv"] = argv

            timeout = {
                "compile": 300,
                "test": 600,
                "build": 900,
                "run": 120,
            }[stage]

            request = SandboxRequest(
                workload_type=WorkloadType.GENERATED_CODE,
                trust_level=TrustLevel.UNTRUSTED,
                command=tuple(argv),
                working_directory=self.workspace,
                network_enabled=False,
                writable_workspace=False,
                limits=ResourceLimits(
                    cpu_count=self.execution_policy.cpu_count,
                    memory_mb=self.execution_policy.memory_mb,
                    pids=self.execution_policy.pids,
                    timeout_seconds=timeout,
                ),
            )

            completed = self.sandbox_manager.execute(request)

            result.update(
                exit_code=completed.exit_code,
                stdout=completed.stdout[-12000:],
                stderr=completed.stderr[-12000:],
                timed_out=completed.timed_out,
                duration_seconds=completed.duration_seconds,
                runtime_kind=completed.runtime_kind.value,
                isolation_class=completed.isolation_class.value,
            )

            if (
                completed.runtime_kind != RuntimeKind.GVISOR
                or completed.isolation_class
                != IsolationClass.KERNEL_EMULATION
            ):
                result["stderr"] += (
                    "\\nUnexpected sandbox isolation boundary."
                )
            else:
                result["success"] = (
                    completed.exit_code == 0
                    and not completed.timed_out
                )

        except Exception as exc:
            result["stderr"] = (
                f"{type(exc).__name__}: {exc}"
            )[-12000:]

        # Preserve the established Data Engine stage record.
        # A persistence failure must propagate.
        self._record(_STAGE_DATA_TYPES[stage], result)
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
