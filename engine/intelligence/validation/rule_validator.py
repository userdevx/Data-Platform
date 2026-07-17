from __future__ import annotations

from dataclasses import dataclass
from typing import Any


BLOCKED_ROLE_LABEL = "".join(["ass", "istant"])


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue]


class RuntimeRuleValidator:
    DEFAULT_BLOCKED_PHRASES = [
        "I can help you with",
        "Hello. I'm",
        "Hello. I’m",
        "No reason returned",
        "unknown source",
        "context_source",
        BLOCKED_ROLE_LABEL,
    ]

    INVALID_SOURCES = {
        "",
        "unknown",
        "unknown_source",
        "unknown source",
        "context_source",
    }

    def validate_response(
        self,
        payload: dict[str, Any],
        definition: dict[str, Any],
    ) -> ValidationResult:
        validation_config = definition.get("validation", {})
        enabled = bool(validation_config.get("enabled", True))

        if not enabled:
            return ValidationResult(passed=True, issues=[])

        issues: list[ValidationIssue] = []

        answer = str(payload.get("answer") or "").strip()
        source = str(payload.get("source") or "").strip()
        data = payload.get("data")

        require_answer = bool(validation_config.get("require_answer", True))
        require_source = bool(validation_config.get("require_source", True))
        require_structured_data = bool(
            validation_config.get("require_structured_data", True)
        )

        if require_answer and not answer:
            issues.append(
                ValidationIssue(
                    code="empty_answer",
                    message="Response answer is empty.",
                    severity="error",
                )
            )

        if require_source and source.lower() in self.INVALID_SOURCES:
            issues.append(
                ValidationIssue(
                    code="invalid_source",
                    message="Response source is missing or invalid.",
                    severity="error",
                )
            )

        if require_structured_data and not isinstance(data, dict):
            issues.append(
                ValidationIssue(
                    code="missing_data",
                    message="Response data must be an object.",
                    severity="error",
                )
            )

        blocked_phrases = list(
            validation_config.get(
                "blocked_response_phrases",
                self.DEFAULT_BLOCKED_PHRASES,
            )
        )

        if BLOCKED_ROLE_LABEL not in blocked_phrases:
            blocked_phrases.append(BLOCKED_ROLE_LABEL)

        combined_text = " ".join(
            [
                str(payload.get("answer") or ""),
                str(payload.get("source") or ""),
                str(payload.get("capability") or ""),
                str(payload.get("ability") or ""),
            ]
        ).lower()

        for phrase in blocked_phrases:
            clean_phrase = str(phrase).strip()

            if clean_phrase and clean_phrase.lower() in combined_text:
                issues.append(
                    ValidationIssue(
                        code="blocked_phrase",
                        message=f"Blocked phrase detected: {clean_phrase}",
                        severity="error",
                    )
                )

        max_answer_chars = int(validation_config.get("max_answer_chars", 4000))

        if len(answer) > max_answer_chars:
            issues.append(
                ValidationIssue(
                    code="answer_too_long",
                    message=(
                        f"Answer exceeded maximum length of "
                        f"{max_answer_chars} characters."
                    ),
                    severity="warning",
                )
            )

        passed = not any(issue.severity == "error" for issue in issues)

        return ValidationResult(
            passed=passed,
            issues=issues,
        )

    def enforce_response(
        self,
        payload: dict[str, Any],
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        result = self.validate_response(
            payload=payload,
            definition=definition,
        )

        validation_payload = {
            "passed": result.passed,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                }
                for issue in result.issues
            ],
        }

        data = payload.get("data")

        if not isinstance(data, dict):
            data = {}

        data["validation"] = validation_payload

        payload["data"] = data

        if result.passed:
            payload.setdefault("status", "success")
            payload.setdefault("source", "intelligence_runtime")
            payload.setdefault("capability", "unknown")
            payload.setdefault("ability", payload.get("capability", "unknown"))
            payload.setdefault("errors", [])

            self._ensure_structured_fields(payload)
            return payload

        return {
            "response_id": payload.get("response_id", ""),
            "request_id": payload.get("request_id", ""),
            "created_at": payload.get("created_at", ""),
            "instance_id": payload.get("instance_id", ""),
            "instance_name": payload.get("instance_name", ""),
            "instance_role": payload.get("instance_role", ""),
            "ability": "rule_validation",
            "capability": "rule_validation",
            "source": "rule_validator",
            "status": "rejected",
            "answer": (
                "The response violated an active system rule and was blocked "
                "before output."
            ),
            "data": {
                "action": "Blocked invalid response.",
                "explanation": (
                    "The validation layer detected a rule violation before "
                    "the response was returned."
                ),
                "next_step": (
                    "Review validation issues, correct the route or response, "
                    "then run the request again."
                ),
                "validation": validation_payload,
                "original_source": payload.get("source", ""),
                "original_capability": payload.get("capability", ""),
            },
            "errors": [
                issue.message
                for issue in result.issues
                if issue.severity == "error"
            ],
        }

    def _ensure_structured_fields(self, payload: dict[str, Any]) -> None:
        data = payload.get("data")

        if not isinstance(data, dict):
            data = {}
            payload["data"] = data

        data.setdefault("action", payload.get("ability") or "Processed request.")
        data.setdefault(
            "explanation",
            f"Source: {payload.get('source') or 'intelligence_runtime'}",
        )
        data.setdefault(
            "next_step",
            "Review the response or submit another request.",
        )
