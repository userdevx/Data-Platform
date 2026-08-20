from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IntelligenceIdentity:
    instance_id: str
    name: str
    display_name: str
    role: str
    description: str


@dataclass(frozen=True)
class ToolSettings:
    enabled: tuple[str, ...]


@dataclass(frozen=True)
class AbilitySettings:
    enabled: tuple[str, ...]


@dataclass(frozen=True)
class PermissionSettings:
    read_records: bool = True
    write_records: bool = False
    write_history: bool = True
    run_approved_commands: bool = False
    network_access: bool = False
    modify_system_files: bool = False


@dataclass(frozen=True)
class RoutingSettings:
    strategy: str
    priority: tuple[str, ...]
    fallback: str


@dataclass(frozen=True)
class ProviderSettings:
    enabled: bool
    name: str
    model: str | None = None


@dataclass(frozen=True)
class DataEngineSettings:
    enabled: bool
    direct_storage_access: bool
    allowed_operations: tuple[str, ...]


@dataclass(frozen=True)
class MemorySettings:
    enabled: bool = True
    read: bool = True
    write: bool = True
    automatic_recall: bool = True
    source: str = "data_engine"
    storage_owner: str = "data_engine"
    context_budget: int = 1500


@dataclass(frozen=True)
class ResponseSettings:
    include_instance_name: bool = True
    include_role: bool = True
    include_capability: bool = True
    include_source: bool = True
    include_status: bool = True
    include_data: bool = True


@dataclass(frozen=True)
class IntelligenceDefinition:
    version: str
    identity: IntelligenceIdentity
    tools: ToolSettings
    abilities: AbilitySettings
    permissions: PermissionSettings
    routing: RoutingSettings
    provider: ProviderSettings
    data_engine: DataEngineSettings
    response: ResponseSettings
    memory: MemorySettings = field(
        default_factory=MemorySettings
    )
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntelligenceRequest:
    request_id: str
    created_at: str
    source: str
    question: str
    normalized_question: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        question: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> "IntelligenceRequest":
        cleaned = question.strip()

        if not cleaned:
            raise ValueError("The intelligence request cannot be empty.")

        return cls(
            request_id=f"intelligence_request_{uuid4().hex[:16]}",
            created_at=utc_now_iso(),
            source=source,
            question=cleaned,
            normalized_question=" ".join(cleaned.lower().split()),
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntelligenceResponse:
    response_id: str
    request_id: str
    created_at: str
    instance_id: str
    instance_name: str
    instance_role: str
    ability: str
    capability: str
    source: str
    status: str
    answer: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        request: IntelligenceRequest,
        instance_id: str,
        instance_name: str,
        instance_role: str,
        ability: str,
        capability: str,
        source: str,
        status: str,
        answer: str,
        data: dict[str, Any] | None = None,
        errors: list[str] | None = None,
    ) -> "IntelligenceResponse":
        return cls(
            response_id=f"intelligence_response_{uuid4().hex[:16]}",
            request_id=request.request_id,
            created_at=utc_now_iso(),
            instance_id=instance_id,
            instance_name=instance_name,
            instance_role=instance_role,
            ability=ability,
            capability=capability,
            source=source,
            status=status,
            answer=answer,
            data=data or {},
            errors=errors or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
