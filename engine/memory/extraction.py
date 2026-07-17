from __future__ import annotations

import re

from engine.memory.models import MemoryCandidate, MemoryKind, MemoryOperation


class RuleBasedMemoryExtractor:
    def extract(
        self,
        *,
        user_id: str,
        intelligence_id: str,
        conversation_id: str,
        message_id: str,
        text: str,
    ) -> list[MemoryCandidate]:
        cleaned = text.strip()

        if not cleaned:
            return []

        lowered = cleaned.lower()
        candidates: list[MemoryCandidate] = []
        explicit_remember = self._is_remember_request(lowered)

        if self._is_forget_request(lowered):
            forget_candidate = self._extract_forget_candidate(
                user_id=user_id,
                intelligence_id=intelligence_id,
                conversation_id=conversation_id,
                message_id=message_id,
                text=cleaned,
            )

            if forget_candidate:
                candidates.append(forget_candidate)

            return candidates

        language = self._extract_language_preference(cleaned)

        if language:
            candidates.append(
                MemoryCandidate(
                    user_id=user_id,
                    intelligence_id=intelligence_id,
                    namespace="implementation_preferences",
                    kind=MemoryKind.PROCEDURAL,
                    subject="user",
                    predicate="preferred_implementation_language",
                    value=language,
                    canonical_text=f"The user prefers {language} implementations.",
                    confidence=0.98,
                    importance=0.90,
                    source_conversation_id=conversation_id,
                    source_message_id=message_id,
                    source_text=cleaned,
                    explicit_request=explicit_remember,
                )
            )

        project_rule = self._extract_project_rule(cleaned)

        if project_rule:
            candidates.append(
                MemoryCandidate(
                    user_id=user_id,
                    intelligence_id=intelligence_id,
                    namespace="project_rules",
                    kind=MemoryKind.PROCEDURAL,
                    subject="active_project",
                    predicate="project_rule",
                    value=project_rule,
                    canonical_text=project_rule,
                    confidence=0.96,
                    importance=0.95,
                    source_conversation_id=conversation_id,
                    source_message_id=message_id,
                    source_text=cleaned,
                    explicit_request=explicit_remember,
                )
            )

        return candidates

    @staticmethod
    def _is_remember_request(text: str) -> bool:
        phrases = (
            "remember that",
            "remember this",
            "save this",
            "store this",
            "add this to memory",
            "from now on",
            "going forward",
        )

        return any(phrase in text for phrase in phrases)

    @staticmethod
    def _is_forget_request(text: str) -> bool:
        phrases = (
            "forget that",
            "forget this",
            "remove this memory",
            "delete this memory",
            "do not remember",
        )

        return any(phrase in text for phrase in phrases)

    @staticmethod
    def _extract_language_preference(text: str) -> str | None:
        patterns = (
            r"\bI prefer ([A-Za-z0-9+#.-]+)\b",
            r"\buse ([A-Za-z0-9+#.-]+) for implementation\b",
            r"\bimplement(?:ation)?s? (?:must|should) use ([A-Za-z0-9+#.-]+)\b",
        )

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return match.group(1)

        return None

    @staticmethod
    def _extract_project_rule(text: str) -> str | None:
        lowered = text.lower()

        rule_signals = (
            "must not",
            "never hardcode",
            "should never",
            "always use",
            "do not use",
            "from now on",
            "going forward",
            "data engine is the",
            "single source of truth",
        )

        if any(signal in lowered for signal in rule_signals):
            return text[:1000]

        return None

    @staticmethod
    def _extract_forget_candidate(
        *,
        user_id: str,
        intelligence_id: str,
        conversation_id: str,
        message_id: str,
        text: str,
    ) -> MemoryCandidate | None:
        lowered = text.lower()

        if "preferred implementation language" in lowered:
            predicate = "preferred_implementation_language"
            namespace = "implementation_preferences"
        elif "project rule" in lowered:
            predicate = "project_rule"
            namespace = "project_rules"
        else:
            return None

        return MemoryCandidate(
            user_id=user_id,
            intelligence_id=intelligence_id,
            namespace=namespace,
            kind=MemoryKind.PROCEDURAL,
            subject="user",
            predicate=predicate,
            value=None,
            canonical_text=text,
            confidence=1.0,
            importance=1.0,
            source_conversation_id=conversation_id,
            source_message_id=message_id,
            source_text=text,
            explicit_request=True,
            operation=MemoryOperation.RETRACT,
        )
