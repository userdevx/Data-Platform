from __future__ import annotations

import json
from pathlib import Path

from engine.intelligence.models import (
    AbilitySettings,
    DataEngineSettings,
    IntelligenceDefinition,
    MemorySettings,
    IntelligenceIdentity,
    PermissionSettings,
    ProviderSettings,
    ResponseSettings,
    RoutingSettings,
    ToolSettings,
)


class IntelligenceDefinitionLoader:
    def load(self, path: Path) -> IntelligenceDefinition:
        if not path.exists():
            raise FileNotFoundError(
                f"Intelligence definition was not found: {path}"
            )

        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        identity = raw["identity"]
        provider = raw.get("provider", {})
        memory = raw.get("memory", {})

        return IntelligenceDefinition(
            version=str(raw["version"]),
            identity=IntelligenceIdentity(
                instance_id=str(identity["id"]),
                name=str(identity["name"]),
                display_name=str(identity["display_name"]),
                role=str(identity["role"]),
                description=str(identity["description"]),
            ),
            tools=ToolSettings(
                enabled=tuple(raw.get("tools", {}).get("enabled", []))
            ),
            abilities=AbilitySettings(
                enabled=tuple(raw.get("abilities", {}).get("enabled", []))
            ),
            permissions=PermissionSettings(
                **raw.get("permissions", {})
            ),
            routing=RoutingSettings(
                strategy=str(raw["routing"]["strategy"]),
                priority=tuple(raw["routing"].get("priority", [])),
                fallback=str(raw["routing"]["fallback"]),
            ),
            provider=ProviderSettings(
                enabled=bool(provider.get("enabled", False)),
                name=str(provider.get("name", "disabled")),
                model=provider.get("model"),
            ),
            data_engine=DataEngineSettings(
                enabled=bool(raw["data_engine"].get("enabled", True)),
                direct_storage_access=bool(
                    raw["data_engine"].get("direct_storage_access", False)
                ),
                allowed_operations=tuple(
                    raw["data_engine"].get("allowed_operations", [])
                ),
            ),
            response=ResponseSettings(
                **raw.get("response", {})
            ),
            memory=MemorySettings(
                enabled=bool(
                    memory.get("enabled", True)
                ),
                read=bool(
                    memory.get("read", True)
                ),
                write=bool(
                    memory.get("write", True)
                ),
                automatic_recall=bool(
                    memory.get(
                        "automatic_recall",
                        True,
                    )
                ),
                source=str(
                    memory.get(
                        "source",
                        "data_engine",
                    )
                ),
                storage_owner=str(
                    memory.get(
                        "storage_owner",
                        "data_engine",
                    )
                ),
                context_budget=int(
                    memory.get(
                        "context_budget",
                        1500,
                    )
                ),
            ),
            metadata=raw.get("metadata", {}),
        )
