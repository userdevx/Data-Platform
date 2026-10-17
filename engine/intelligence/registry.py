from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.intelligence.capabilities.builtins import (
    get_capability,
)
from engine.intelligence.tools.knowledge_search import (
    SearchKnowledgeTool,
)
from engine.tools.file_tools import (
    ListManagedFilesTool,
    ReadManagedFilesTool,
    WriteManagedFilesTool,
)


@dataclass(frozen=True)
class AbilityDefinition:
    name: str
    capability_name: str
    required_tools: tuple[str, ...]

    @property
    def capability(self):
        return get_capability(
            self.capability_name
        )

    def resolve_capability(
        self,
        *_args: Any,
        **_kwargs: Any,
    ):
        return get_capability(
            self.capability_name
        )


class AbilityRegistry:
    def __init__(self) -> None:
        self._abilities = {
            "identify_instance": AbilityDefinition(
                name="identify_instance",
                capability_name="identity",
                required_tools=(),
            ),
            "answer_datetime_questions": AbilityDefinition(
                name=(
                    "answer_datetime_questions"
                ),
                capability_name="datetime",
                required_tools=(),
            ),
            "manage_memory": AbilityDefinition(
                name="manage_memory",
                capability_name=(
                    "memory_command"
                ),
                required_tools=(
                    "query_data_engine",
                ),
            ),
            "report_system_health": AbilityDefinition(
                name=(
                    "report_system_health"
                ),
                capability_name=(
                    "system_status"
                ),
                required_tools=(
                    "read_system_status",
                ),
            ),
            "answer_record_questions": AbilityDefinition(
                name=(
                    "answer_record_questions"
                ),
                capability_name=(
                    "record_query"
                ),
                required_tools=(
                    "query_data_engine",
                ),
            ),
            "retrieve_platform_knowledge": AbilityDefinition(
                name=(
                    "retrieve_platform_knowledge"
                ),
                capability_name=(
                    "knowledge_search"
                ),
                required_tools=(
                    "search_knowledge",
                ),
            ),
            "search_public_sources": AbilityDefinition(
                name=(
                    "search_public_sources"
                ),
                capability_name=(
                    "public_source_search"
                ),
                required_tools=(
                    "public_source_search",
                ),
            ),
            "application_generation": AbilityDefinition(
                name=(
                    "application_generation"
                ),
                capability_name=(
                    "application_generation"
                ),
                required_tools=(
                    "list_files",
                    "read_files",
                    "write_files",
                ),
            ),
            "model_reasoning": AbilityDefinition(
                name="model_reasoning",
                capability_name=(
                    "model_reasoning"
                ),
                required_tools=(),
            ),
        }

    def get(
        self,
        name: str,
    ) -> AbilityDefinition | None:
        return self._abilities.get(
            name
        )

    def has(
        self,
        name: str,
    ) -> bool:
        return (
            name in self._abilities
        )

    def names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._abilities.keys()
        )

    def all(
        self,
    ) -> dict[
        str,
        AbilityDefinition,
    ]:
        return dict(
            self._abilities
        )

    def get_capability(
        self,
        name: str,
    ):
        return get_capability(
            name
        )


try:
    from engine.communication.email.tool import (
        EmailReadTool,
    )
except Exception:
    EmailReadTool = None

class ToolRegistry:
    def __init__(
        self,
    ) -> None:
        self._tools: dict[
            str,
            object,
        ] = {
            "read_system_status": object(),
            "query_data_engine": object(),
            "search_knowledge": (
                SearchKnowledgeTool()
            ),
            "public_source_search": object(),
            "write_intelligence_history": object(),
            **(
                {"email_read": EmailReadTool()}
                if EmailReadTool is not None
                else {}
            ),
            "list_files": (
                ListManagedFilesTool()
            ),
            "read_files": (
                ReadManagedFilesTool()
            ),
            "write_files": (
                WriteManagedFilesTool()
            ),
        }

    def get(
        self,
        name: str,
    ) -> object:
        tool = self._tools.get(
            name
        )

        if tool is None:
            raise KeyError(
                "Tool is not registered: "
                + name
            )

        return tool

    def has(
        self,
        name: str,
    ) -> bool:
        return (
            name in self._tools
        )

    def names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._tools.keys()
        )

    def all(
        self,
    ) -> dict[str, object]:
        return dict(
            self._tools
        )
