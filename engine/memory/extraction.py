from __future__ import annotations

import re

from engine.memory.models import MemoryCandidate, MemoryKind, MemoryOperation


class RuleBasedMemoryExtractor:
    """Extract supported long-term memory candidates from user messages."""

    _LANGUAGE_TOKEN = r"[A-Za-z][A-Za-z0-9+#.-]*"

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

            if forget_candidate is not None:
                candidates.append(forget_candidate)

            return candidates

        language = self._extract_language_preference(cleaned)

        if language is not None:
            candidates.append(
                MemoryCandidate(
                    user_id=user_id,
                    intelligence_id=intelligence_id,
                    namespace="implementation_preferences",
                    kind=MemoryKind.PROCEDURAL,
                    subject="user",
                    predicate="preferred_implementation_language",
                    value=language,
                    canonical_text=(
                        f"The user prefers {language} for implementation examples."
                    ),
                    confidence=0.98,
                    importance=0.90,
                    source_conversation_id=conversation_id,
                    source_message_id=message_id,
                    source_text=cleaned,
                    explicit_request=explicit_remember,
                )
            )

        project_rule = self._extract_project_rule(cleaned)

        if project_rule is not None:
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
            "remember my preference",
            "save this",
            "save my preference",
            "store this",
            "store my preference",
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
            "forget my preference",
            "remove this memory",
            "delete this memory",
            "do not remember",
        )

        return any(phrase in text for phrase in phrases)

    @classmethod
    def _extract_language_preference(cls, text: str) -> str | None:
        token = cls._LANGUAGE_TOKEN

        patterns = (
            rf"\bI prefer\s+({token})\b",
            rf"\bmy preference is\s+({token})\b",
            rf"\bpreferred implementation language is\s+({token})\b",
            rf"\buse\s+({token})\s+for implementation(?:s|\s+examples)?\b",
            rf"\bimplementation(?:s|\s+examples)?\s+"
            rf"(?:must|should)\s+use\s+({token})\b",
            rf"\bimplementation examples\s+"
            rf"(?:must|should)\s+(?:be written in|use)\s+({token})\b",
            rf"\bcode examples\s+"
            rf"(?:must|should)\s+(?:be written in|use)\s+({token})\b",
            rf"\bexamples\s+(?:must|should)\s+use\s+({token})\b",
        )

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match is not None:
                return cls._normalize_language(match.group(1))

        return None

    @staticmethod
    def _normalize_language(language: str) -> str:
        aliases = {
            "python": "Python",
            "javascript": "JavaScript",
            "typescript": "TypeScript",
            "rust": "Rust",
            "java": "Java",
            "c++": "C++",
            "c#": "C#",
            "go": "Go",
            "golang": "Go",
        }

        cleaned = language.strip()
        return aliases.get(cleaned.lower(), cleaned)

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

        language_signals = (
            "preferred implementation language",
            "implementation language",
            "python preference",
            "coding language preference",
            "implementation preference",
        )

        if any(signal in lowered for signal in language_signals):
            predicate = "preferred_implementation_language"
            namespace = "implementation_preferences"
            subject = "user"
        elif "project rule" in lowered:
            predicate = "project_rule"
            namespace = "project_rules"
            subject = "active_project"
        else:
            return None

        return MemoryCandidate(
            user_id=user_id,
            intelligence_id=intelligence_id,
            namespace=namespace,
            kind=MemoryKind.PROCEDURAL,
            subject=subject,
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
