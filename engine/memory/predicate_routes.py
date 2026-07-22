from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ROUTE_PATH = Path("config/memory/predicate_routes.json")


class PredicateRouteConfigurationError(RuntimeError):
    """Raised when predicate-route configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class PredicateRoute:
    predicate: str
    namespace: str
    subject: str
    answer_mode: str
    patterns: tuple[str, ...]


def normalize_lookup_text(text: str) -> str:
    normalized = text.casefold().strip()
    normalized = re.sub(r"[^\w\s']", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _require_string(
    value: Any,
    *,
    route_name: str,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PredicateRouteConfigurationError(
            f"Route '{route_name}' has an invalid '{field_name}' field."
        )

    return value.strip()


def _parse_route(
    predicate: str,
    raw_route: Any,
) -> PredicateRoute:
    if not isinstance(raw_route, dict):
        raise PredicateRouteConfigurationError(
            f"Route '{predicate}' must be a JSON object."
        )

    namespace = _require_string(
        raw_route.get("namespace"),
        route_name=predicate,
        field_name="namespace",
    )

    subject = _require_string(
        raw_route.get("subject", "user"),
        route_name=predicate,
        field_name="subject",
    )

    answer_mode = _require_string(
        raw_route.get("answer_mode", "value"),
        route_name=predicate,
        field_name="answer_mode",
    )

    if answer_mode not in {"value", "canonical_text"}:
        raise PredicateRouteConfigurationError(
            f"Route '{predicate}' has unsupported answer_mode "
            f"'{answer_mode}'."
        )

    raw_patterns = raw_route.get("patterns")

    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise PredicateRouteConfigurationError(
            f"Route '{predicate}' must define at least one pattern."
        )

    patterns: list[str] = []

    for raw_pattern in raw_patterns:
        pattern = _require_string(
            raw_pattern,
            route_name=predicate,
            field_name="patterns",
        )

        normalized_pattern = normalize_lookup_text(pattern)

        if normalized_pattern not in patterns:
            patterns.append(normalized_pattern)

    return PredicateRoute(
        predicate=predicate,
        namespace=namespace,
        subject=subject,
        answer_mode=answer_mode,
        patterns=tuple(patterns),
    )


def load_predicate_routes(
    *,
    root: Path,
    relative_path: Path = DEFAULT_ROUTE_PATH,
) -> dict[str, PredicateRoute]:
    route_path = root / relative_path

    if not route_path.is_file():
        raise PredicateRouteConfigurationError(
            f"Predicate route configuration not found: {route_path}"
        )

    try:
        payload = json.loads(
            route_path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise PredicateRouteConfigurationError(
            f"Predicate route configuration contains invalid JSON: {error}"
        ) from error

    if not isinstance(payload, dict):
        raise PredicateRouteConfigurationError(
            "Predicate route configuration must be a JSON object."
        )

    if payload.get("schema_version") != 1:
        raise PredicateRouteConfigurationError(
            "Unsupported predicate-route schema version."
        )

    raw_routes = payload.get("routes")

    if not isinstance(raw_routes, dict) or not raw_routes:
        raise PredicateRouteConfigurationError(
            "Predicate route configuration contains no routes."
        )

    routes: dict[str, PredicateRoute] = {}

    for predicate, raw_route in raw_routes.items():
        if not isinstance(predicate, str) or not predicate.strip():
            raise PredicateRouteConfigurationError(
                "Every predicate route requires a non-empty name."
            )

        clean_predicate = predicate.strip()

        routes[clean_predicate] = _parse_route(
            clean_predicate,
            raw_route,
        )

    return routes


def match_predicate_route(
    *,
    root: Path,
    text: str,
) -> PredicateRoute | None:
    normalized_text = normalize_lookup_text(text)

    if not normalized_text:
        return None

    routes = load_predicate_routes(root=root)

    best_route: PredicateRoute | None = None
    best_pattern_length = -1

    for route in routes.values():
        for pattern in route.patterns:
            if (
                pattern == normalized_text
                or pattern in normalized_text
            ):
                if len(pattern) > best_pattern_length:
                    best_route = route
                    best_pattern_length = len(pattern)

    return best_route
