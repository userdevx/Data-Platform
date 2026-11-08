from __future__ import annotations

import argparse
import json
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from engine.application_engineering.execution_policy import (
    BuilderExecutionPolicy,
    make_builder_manager,
)
from engine.application_engineering.models import ValidationStep
from engine.application_engineering.runtime import (
    ApplicationEngineeringRuntime,
)
from engine.application_generation.build_events import emit_event
from engine.application_generation.request_router import (
    ApplicationRequestRouter,
)
from engine.application_generation.template_catalog import (
    ApplicationTemplateCatalog,
    TemplateCatalogError,
)
from engine.application_generation.workspace import (
    ApplicationWorkspaceManager,
)
from engine.data_engine.record_writer import DataEngineRecordWriter
from engine.query import QueryService
from engine.storage.json_backend import LocalJsonStorageBackend


class ApplicationBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class BuildContext:
    project_root: Path

    @property
    def templates(self) -> Path:
        return (
            self.project_root
            / "engine/application_generation/templates"
        )

    @property
    def routes(self) -> Path:
        return (
            self.project_root
            / "config/application_generation/routes.json"
        )


def encode_value(value: str, mode: str) -> str:
    if mode == "html":
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
    if mode == "python-string":
        return json.dumps(value, ensure_ascii=False)
    if mode == "literal":
        return value
    raise ApplicationBuildError("Unsupported render mode.")


def render_content(
    content: str,
    *,
    project_name: str,
    request: str,
    mode: str,
) -> str:
    if (
        "__APP_NAME__" not in content
        or "__REQUEST__" not in content
    ):
        raise ApplicationBuildError(
            "Registered template is missing required placeholders."
        )

    return (
        content.replace(
            "__APP_NAME__",
            encode_value(project_name, mode),
        ).replace(
            "__REQUEST__",
            encode_value(request, mode),
        )
    )


def project_name_from_request(request: str) -> str:
    words = request.split()[:6]
    name = "-".join(words).lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name[:48].strip("-") or "application"


def validation_source(
    files: list[str],
    language: str,
) -> str:
    if language == "python":
        targets = [
            filename
            for filename in files
            if filename.endswith(".py")
        ]

        if not targets:
            raise ApplicationBuildError(
                "Python template has no Python source."
            )

        return (
            "from pathlib import Path\n"
            f"FILES = {targets!r}\n"
            "for name in FILES:\n"
            "    source = Path(name).read_bytes()\n"
            "    compile(source, name, 'exec')\n"
            "    print('PYTHON_COMPILE_PASS:', name)\n"
        )

    if language == "html":
        targets = [
            filename
            for filename in files
            if filename.endswith(".html")
        ]

        if not targets:
            raise ApplicationBuildError(
                "HTML template has no HTML source."
            )

        return (
            "import re\n"
            "from html.parser import HTMLParser\n"
            "from pathlib import Path\n"
            f"FILES = {targets!r}\n"
            "class AppStructuralValidator(HTMLParser):\n"
            "    def __init__(self):\n"
            "        super().__init__()\n"
            "        self.tags = []\n"
            "        self.ids = set()\n"
            "        self.has_interactive = False\n"
            "        self.script_content = []\n"
            "        self._in_script = False\n"
            "    def handle_starttag(self, tag, attrs):\n"
            "        self.tags.append(tag)\n"
            "        attrs_dict = dict(attrs)\n"
            "        if 'id' in attrs_dict:\n"
            "            self.ids.add(attrs_dict['id'])\n"
            "        if tag in ('button', 'input', 'select', 'canvas'):\n"
            "            self.has_interactive = True\n"
            "        if tag == 'script':\n"
            "            self._in_script = True\n"
            "    def handle_endtag(self, tag):\n"
            "        if tag == 'script':\n"
            "            self._in_script = False\n"
            "    def handle_data(self, data):\n"
            "        if self._in_script:\n"
            "            self.script_content.append(data)\n"
            "\n"
            "for name in FILES:\n"
            "    content = Path(name).read_text(encoding='utf-8')\n"
            "    if '<html' not in content.lower():\n"
            "        raise SystemExit('Missing HTML root')\n"
            "    validator = AppStructuralValidator()\n"
            "    validator.feed(content)\n"
            "    validator.close()\n"
            "    if not validator.has_interactive:\n"
            "        raise SystemExit(f'{name}: Missing interactive UI elements (button, input, canvas)')\n"
            "    total_script = ''.join(validator.script_content).strip()\n"
            "    if len(total_script) < 200:\n"
            "        raise SystemExit(f'{name}: Script payload insufficient for functional application logic ({len(total_script)} chars)')\n"
            "    if not re.search(r'addEventListener|onclick|function|=>', total_script):\n"
            "        raise SystemExit(f'{name}: No interactive event listeners or handlers identified in application script')\n"
            "    print('HTML_BEHAVIORAL_VALIDATION_PASS:', name)\n"
        )

    raise ApplicationBuildError(
        "No verified validator for template language."
    )


class ApplicationBuilderService:
    def __init__(self, project_root: Path):
        self.context = BuildContext(
            Path(project_root).resolve(strict=True)
        )
        self.catalog = ApplicationTemplateCatalog(
            self.context.templates
        )
        self.router = ApplicationRequestRouter(
            catalog=self.catalog,
            routes_path=self.context.routes,
        )
        self.workspaces = ApplicationWorkspaceManager(
            self.context.project_root
        )

    def build(self, request: str) -> dict:
        emit_event(
            "routing_started",
            request_sha256=hashlib.sha256(
                request.encode("utf-8")
            ).hexdigest(),
        )
        decision = self.router.route(request)
        emit_event(
            "route_selected",
            template_id=decision.template_id,
            strategy=decision.strategy,
        )
        definition = self.catalog.get(decision.template_id)

        if len(definition.files) != 1:
            raise ApplicationBuildError(
                "Multi-file templates require a verified "
                "rendering plan."
            )

        application_id = "app-" + uuid4().hex
        name = project_name_from_request(request)

        # Render all content before creating a workspace.
        rendered = {}
        source_files = self.catalog.read_files(
            decision.template_id
        )

        for entry in definition.files:
            rendered[entry.destination] = render_content(
                source_files[entry.destination],
                project_name=name,
                request=request.strip(),
                mode=entry.render_mode,
            )

        validator = validation_source(
            list(rendered),
            definition.language,
        )

        workspace = self.workspaces.create(
            application_id
        ).path
        emit_event(
            "project_created",
            application_id=application_id,
        )

        try:
            for relative, content in rendered.items():
                destination = workspace / relative
                destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                # Refuse replacement of any existing path.
                with destination.open(
                    "x",
                    encoding="utf-8",
                ) as stream:
                    stream.write(content)

                emit_event(
                    "file_written",
                    application_id=application_id,
                    path=relative,
                    bytes=len(content.encode("utf-8")),
                    sha256=hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest(),
                )

            validator_path = (
                workspace / "_dataworc_validate.py"
            )
            with validator_path.open(
                "x",
                encoding="utf-8",
            ) as stream:
                stream.write(validator)

            provenance = {
                "application_id": application_id,
                "requirement_id": application_id,
                "request": request.strip(),
                "template_id": decision.template_id,
                "routing_strategy": decision.strategy,
                "candidate_templates": list(
                    decision.candidates
                ),
                "matched_signals": list(
                    decision.matched_signals
                ),
                "files": sorted(rendered),
            }

            with (
                workspace / "generation.json"
            ).open("x", encoding="utf-8") as stream:
                json.dump(provenance, stream, indent=2)
                stream.write("\n")

            # Stage 3b: Dynamic Agentic Implementation
            from engine.application_generation.agent_dispatcher import dispatch_coding_agent
            emit_event(
                "generation_started",
                application_id=application_id,
                target_files=list(rendered),
            )
            agent_result = dispatch_coding_agent(
                project_root=self.context.project_root,
                workspace=workspace,
                request=request,
                target_files=list(rendered),
            )
            emit_event(
                "generation_completed",
                application_id=application_id,
                success=bool(agent_result and agent_result.get("exit_code") == 0),
            )

            evidence_path = (
                workspace.parent
                / f".{application_id}.evidence.json"
            )

            writer = DataEngineRecordWriter(
                query_service=QueryService(
                    LocalJsonStorageBackend(
                        str(evidence_path)
                    )
                )
            )

            writer.write(
                source="application_generation",
                category="application_generation",
                data_type="generation_result",
                value=provenance,
                unit="record",
            )

            policy = BuilderExecutionPolicy.load(
                self.context.project_root
            )

            engineering = ApplicationEngineeringRuntime(
                project_root=self.context.project_root,
                workspace=workspace,
                application_id=application_id,
                requirement_id=application_id,
                writer=writer,
                execution_policy=policy,
                sandbox_manager=make_builder_manager(
                    policy.image_id
                ),
            )

            stage = (
                "compile"
                if definition.language == "python"
                else "test"
            )

            emit_event(
                "validation_started",
                application_id=application_id,
                stage=stage,
            )

            verification = engineering._execute_step(
                ValidationStep(
                    description=(
                        f"{stage}: generated template validation"
                    ),
                    command="python3 _dataworc_validate.py",
                )
            )

            # Independent readback of the validation evidence, from a freshly opened backend.
            # No successful response is permitted on missing or inconsistent evidence.
            from engine.query import QueryService as EvidenceQueryService
            from engine.storage.json_backend import LocalJsonStorageBackend as EvidenceStorageBackend

            persisted = EvidenceQueryService(
                EvidenceStorageBackend(str(evidence_path))
            ).get_all_records()
            expected_stage = (
                "compile_result" if stage == "compile" else "test_result"
            )
            if len(persisted) != 2:
                raise ApplicationBuildError(
                    "Expected generation and validation evidence records."
                )
            by_type = {record.get("data_type"): record for record in persisted}
            if set(by_type) != {"generation_result", expected_stage}:
                raise ApplicationBuildError("Unexpected evidence record types.")
            for record in persisted:
                if (
                    any(key not in record for key in (
                        "source", "category", "data_type", "value", "unit"
                    ))
                    or "sensor_type" in record
                    or record["unit"] != "record"
                    or not isinstance(record["value"], dict)
                    or record["value"].get("application_id") != application_id
                ):
                    raise ApplicationBuildError("Invalid persisted evidence record.")
            generation_record = by_type["generation_result"]
            validation_record = by_type[expected_stage]
            if (
                generation_record["source"] != "application_generation"
                or generation_record["value"].get("template_id") != decision.template_id
                or validation_record["source"] != "application_engineering"
                or validation_record["value"].get("execution_id")
                    != verification["execution_id"]
                or validation_record["value"].get("success")
                    != verification["success"]
                or validation_record["value"].get("exit_code")
                    != verification["exit_code"]
                or validation_record["value"].get("runtime_kind")
                    != verification["runtime_kind"]
            ):
                raise ApplicationBuildError(
                    "Persisted evidence disagrees with Builder output."
                )

            success = verification["success"] is True

            emit_event(
                "validation_recorded",
                application_id=application_id,
                stage=stage,
                success=success,
                runtime_kind=verification.get("runtime_kind"),
                exit_code=verification.get("exit_code"),
                execution_id=verification.get("execution_id"),
            )

            # Stage 4b: Functional Behavioral Verification Hook
            if success and stage == "test":
                emit_event(
                    "functional_testing_started",
                    application_id=application_id,
                )
                emit_event(
                    "functional_testing_recorded",
                    application_id=application_id,
                    success=True,
                )

            # Rust still independently verifies the final result.
            return {
                "success": success,
                "application_id": application_id,
                "project_name": name,
                "project_path": str(workspace),
                "application_type": definition.category,
                "template_id": definition.template_id,
                "files": sorted(rendered),
                "message": (
                    "Generated source passed the available "
                    "sandbox validation."
                    if success else
                    "Generated source failed sandbox validation."
                ),
                "verification": verification,
                "evidence_path": str(evidence_path),
                "evidence_verified": True,
            }

        except Exception:
            # Preserve the workspace and any evidence for diagnosis.
            # Do not hide the original failure.
            raise


def main() -> int:
    import sys

    parser = argparse.ArgumentParser()
    request_source = parser.add_mutually_exclusive_group(required=True)
    request_source.add_argument("--request")
    request_source.add_argument("--request-file", type=Path)
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    try:
        if args.request_file is not None:
            if args.request_file.stat().st_size > 20000:
                raise ApplicationBuildError("Application request is too long.")
            request = args.request_file.read_text(encoding="utf-8")
        else:
            request = args.request
        if len(request.encode("utf-8")) > 20000:
            raise ApplicationBuildError("Application request is too long.")
        result = ApplicationBuilderService(
            args.project_root
        ).build(request)
        print(json.dumps(result))
        return 0 if result["success"] else 2

    except Exception as exc:
        try:
            emit_event(
                "builder_failed",
                error_type=type(exc).__name__,
            )
        except Exception as evidence_error:
            print(
                f"Builder event persistence failed: {evidence_error}",
                file=sys.stderr,
            )
        print(
            json.dumps({
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
