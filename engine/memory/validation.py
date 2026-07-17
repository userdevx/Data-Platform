from __future__ import annotations

import re
from dataclasses import replace
from datetime import timedelta

from engine.memory.models import MemoryCandidate, ValidationResult, utc_now
from engine.memory.predicates import TemporalMode, get_predicate_definition


SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(
        r"\b(?:password|passwd|api[_ -]?key|secret|token)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
)


class MemoryValidator:
    def validate(self, candidate: MemoryCandidate) -> tuple[ValidationResult, MemoryCandidate]:
        if candidate.confidence < 0.75:
            return ValidationResult.reject("low_confidence"), candidate

        if candidate.importance < 0.40 and not candidate.explicit_request:
            return ValidationResult.reject("low_future_value"), candidate

        if self._contains_secret(candidate.source_text):
            return ValidationResult.reject("possible_secret"), candidate

        predicate = get_predicate_definition(candidate.predicate)

        if predicate is None:
            return ValidationResult.reject("unknown_predicate"), candidate

        if not predicate.extraction_enabled and not candidate.explicit_request:
            return ValidationResult.reject("automatic_extraction_disabled"), candidate

        if predicate.requires_explicit_consent and not candidate.explicit_request:
            return ValidationResult.reject("consent_required"), candidate

        validated = candidate

        if (
            predicate.temporal_mode is TemporalMode.TIME_BOUND
            and candidate.valid_until is None
            and predicate.default_ttl_seconds is not None
        ):
            valid_from = candidate.valid_from or utc_now()
            validated = replace(
                candidate,
                valid_from=valid_from,
                valid_until=valid_from + timedelta(seconds=predicate.default_ttl_seconds),
            )

        return ValidationResult.accept(sensitivity=predicate.sensitivity), validated

    @staticmethod
    def _contains_secret(text: str) -> bool:
        return any(pattern.search(text) for pattern in SECRET_PATTERNS)
