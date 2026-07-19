from __future__ import annotations

from dataclasses import dataclass

from engine.intelligence.memory_runtime import (
    is_explicit_memory_command,
)
from engine.intelligence.models import IntelligenceRequest


@dataclass(frozen=True)
class IntelligenceRoute:
    ability_name: str | None
    reason: str
    confidence: float


class IntelligenceRouter:
    def route(
        self,
        request: IntelligenceRequest,
        enabled_abilities: tuple[str, ...],
        priority: tuple[str, ...],
    ) -> IntelligenceRoute:
        text = request.normalized_question

        # Deterministic routes must run before model reasoning.
        if self._datetime(text) and "answer_datetime_questions" in enabled_abilities:
            return IntelligenceRoute(
                ability_name="answer_datetime_questions",
                reason="Matched route: datetime",
                confidence=0.98,
            )

        if (
            self._public_source_search(text)
            and "search_public_sources" in enabled_abilities
        ):
            return IntelligenceRoute(
                ability_name="search_public_sources",
                reason="Matched route: public_source_search",
                confidence=0.95,
            )

        checks = {
            "identity": self._identity,
            "datetime": self._datetime,
            "memory_command": self._memory_command,
            "system_status": self._system_status,
            "record_query": self._record_query,
            "knowledge_search": self._knowledge_search,
            "public_source_search": self._public_source_search,
            "model_reasoning": self._model_reasoning,
        }

        ability_map = {
            "identity": "identify_instance",
            "datetime": "answer_datetime_questions",
            "memory_command": "manage_memory",
            "system_status": "report_system_health",
            "record_query": "answer_record_questions",
            "knowledge_search": "retrieve_platform_knowledge",
            "public_source_search": "search_public_sources",
            "model_reasoning": "model_reasoning",
        }

        for route_name in priority:
            check = checks.get(route_name)

            if check is None:
                continue

            if check(text):
                ability_name = ability_map.get(route_name)

                if ability_name in enabled_abilities:
                    return IntelligenceRoute(
                        ability_name=ability_name,
                        reason=f"Matched route: {route_name}",
                        confidence=0.90,
                    )

        if "model_reasoning" in enabled_abilities:
            return IntelligenceRoute(
                ability_name="model_reasoning",
                reason="Fallback routed request to model reasoning.",
                confidence=0.55,
            )

        return IntelligenceRoute(
            ability_name=None,
            reason="No enabled ability matched the request.",
            confidence=0.0,
        )

    def _memory_command(self, text: str) -> bool:
        return is_explicit_memory_command(text)

    def _datetime(self, text: str) -> bool:
        phrases = [
            "today's date",
            "todays date",
            "what is today's date",
            "what is todays date",
            "what is the date",
            "current date",
            "date today",
            "what day is it",
            "what day is today",
            "current day",
            "what time is it",
            "current time",
            "time now",
        ]

        return any(phrase in text for phrase in phrases)

    def _identity(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "who are you",
                "what are you",
                "your name",
                "identify yourself",
            ]
        )

    def _system_status(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "system status",
                "check status",
                "health",
                "operating",
                "runtime status",
                "platform status",
            ]
        )

    def _record_query(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "what records",
                "show records",
                "list records",
                "count records",
                "query records",
                "find records",
                "stored records",
                "stored data",
                "query data",
                "show data",
                "list data",
                "count data",
            ]
        )

    def _knowledge_search(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "knowledge",
                "project notes",
                "explain platform",
                "platform components",
                "what is the data platform",
                "what is data platform",
            ]
        )

    def _public_source_search(self, text: str) -> bool:
        has_public_source = any(
            source in text
            for source in [
                "instagram",
                "youtube",
                "spotify",
                "facebook",
                "tiktok",
                "twitter",
                "web",
                "internet",
            ]
        )

        has_source_request = any(
            phrase in text
            for phrase in [
                "search",
                "find",
                "look up",
                "lookup",
                "who is",
                "what is",
                "profile",
                "account",
                "handle",
                "official",
                "link",
                "bio",
                "posts",
            ]
        )

        return has_public_source and has_source_request

    def _model_reasoning(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in [
                "create",
                "generate",
                "write",
                "plan",
                "explain",
                "summarize",
                "design",
                "build",
                "make",
                "how to",
                "steps",
                "guide",
                "recommend",
                "outline",
                "draft",
                "hello",
                "how are you",
            ]
        )
