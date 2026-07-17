from __future__ import annotations

from typing import Any

from engine.intelligence.models import (
    IntelligenceDefinition,
    IntelligenceRequest,
    IntelligenceResponse,
)


class IntelligenceInstance:
    def __init__(
        self,
        definition: IntelligenceDefinition,
        data_engine,
        tool_registry,
        ability_registry,
        router,
        history_writer,
    ) -> None:
        self.definition = definition
        self.data_engine = data_engine
        self.tool_registry = tool_registry
        self.ability_registry = ability_registry
        self.router = router
        self.history_writer = history_writer

        self._validate_definition()

    @property
    def instance_id(self) -> str:
        return self.definition.identity.instance_id

    @property
    def name(self) -> str:
        return self.definition.identity.name

    @property
    def display_name(self) -> str:
        return self.definition.identity.display_name

    @property
    def role(self) -> str:
        return self.definition.identity.role

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.definition.tools.enabled

    def has_ability(self, ability_name: str) -> bool:
        return ability_name in self.definition.abilities.enabled

    def process(self, request: IntelligenceRequest) -> IntelligenceResponse:
        route = self.router.route(
            request=request,
            enabled_abilities=self.definition.abilities.enabled,
            priority=self.definition.routing.priority,
        )

        if route.ability_name is None:
            response = IntelligenceResponse.create(
                request=request,
                instance_id=self.instance_id,
                instance_name=self.name,
                instance_role=self.role,
                ability="unknown",
                capability="unknown",
                source="intelligence_router",
                status="not_found",
                answer=(
                    f"{self.display_name} could not match the request "
                    "to an enabled ability."
                ),
                data={
                    "reason": route.reason,
                    "confidence": route.confidence,
                },
            )

            self._write_history(request, response)
            return response

        ability = self.ability_registry.get(route.ability_name)

        missing_tools = [
            tool_name
            for tool_name in ability.required_tools
            if not self.has_tool(tool_name)
        ]

        if missing_tools:
            response = IntelligenceResponse.create(
                request=request,
                instance_id=self.instance_id,
                instance_name=self.name,
                instance_role=self.role,
                ability=ability.name,
                capability=ability.capability,
                source="intelligence_permissions",
                status="rejected",
                answer=(
                    f"{self.display_name} does not have the tools "
                    "required for this ability."
                ),
                data={
                    "missing_tools": missing_tools,
                },
            )

            self._write_history(request, response)
            return response

        capability = ability.resolve_capability()

        result = capability.execute(
            request=request,
            instance=self,
        )

        response = IntelligenceResponse.create(
            request=request,
            instance_id=self.instance_id,
            instance_name=self.name,
            instance_role=self.role,
            ability=ability.name,
            capability=str(result.get("capability", ability.capability)),
            source=str(result.get("source", "intelligence_runtime")),
            status=str(result.get("status", "success")),
            answer=str(result.get("answer", "")),
            data=dict(result.get("data", {})),
            errors=list(result.get("errors", [])),
        )

        self._write_history(request, response)
        return response

    def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ):
        if not self.has_tool(tool_name):
            raise PermissionError(f"Tool is not enabled: {tool_name}")

        tool = self.tool_registry.get(tool_name)

        return tool.execute(
            arguments=arguments,
            context={
                "instance_id": self.instance_id,
                "instance_name": self.name,
                "instance_role": self.role,
            },
        )

    def _write_history(
        self,
        request: IntelligenceRequest,
        response: IntelligenceResponse,
    ) -> None:
        if not self.definition.permissions.write_history:
            return

        self.history_writer.write(
            request=request,
            response=response,
        )

    def _validate_definition(self) -> None:
        identity = self.definition.identity

        if not identity.instance_id.strip():
            raise ValueError("The Intelligence Definition requires an id.")

        if not identity.name.strip():
            raise ValueError("The Intelligence Definition requires a name.")

        configured_tools = set(self.definition.tools.enabled)
        registered_tools = set(self.tool_registry.names())
        unknown_tools = configured_tools - registered_tools

        if unknown_tools:
            raise ValueError(
                "Unregistered tools were configured: "
                f"{sorted(unknown_tools)}"
            )

        configured_abilities = set(self.definition.abilities.enabled)
        registered_abilities = set(self.ability_registry.names())
        unknown_abilities = configured_abilities - registered_abilities

        if unknown_abilities:
            raise ValueError(
                "Unregistered abilities were configured: "
                f"{sorted(unknown_abilities)}"
            )
