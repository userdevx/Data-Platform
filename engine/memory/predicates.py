from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PredicateCardinality(str, Enum):
    ONE = "one"
    MANY = "many"


class TemporalMode(str, Enum):
    STABLE = "stable"
    TIME_BOUND = "time_bound"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class PredicateDefinition:
    name: str
    cardinality: PredicateCardinality
    temporal_mode: TemporalMode
    sensitivity: str = "normal"
    extraction_enabled: bool = True
    requires_explicit_consent: bool = False
    default_ttl_seconds: int | None = None
    render_template: str | None = None


PREDICATE_REGISTRY: dict[str, PredicateDefinition] = {
    "preferred_implementation_language": PredicateDefinition(
        name="preferred_implementation_language",
        cardinality=PredicateCardinality.ONE,
        temporal_mode=TemporalMode.STABLE,
        render_template="The user prefers implementations in {value}.",
    ),
    "preferred_response_style": PredicateDefinition(
        name="preferred_response_style",
        cardinality=PredicateCardinality.ONE,
        temporal_mode=TemporalMode.STABLE,
        render_template="The user prefers this response style: {value}.",
    ),
    "preferred_terminology": PredicateDefinition(
        name="preferred_terminology",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.STABLE,
        render_template="Use this preferred terminology: {value}.",
    ),
    "project_rule": PredicateDefinition(
        name="project_rule",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.STABLE,
        render_template="Apply this project rule: {value}.",
    ),
    "prefers_architecture": PredicateDefinition(
        name="prefers_architecture",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.STABLE,
        render_template="The user prefers this architecture principle: {value}.",
    ),
    "active_project": PredicateDefinition(
        name="active_project",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.TIME_BOUND,
        render_template="The user is working on this active project: {value}.",
    ),
    "current_location": PredicateDefinition(
        name="current_location",
        cardinality=PredicateCardinality.ONE,
        temporal_mode=TemporalMode.TIME_BOUND,
        sensitivity="sensitive",
        extraction_enabled=False,
        requires_explicit_consent=True,
        default_ttl_seconds=86_400,
    ),
    "medical_condition": PredicateDefinition(
        name="medical_condition",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.STABLE,
        sensitivity="high",
        extraction_enabled=False,
        requires_explicit_consent=True,
    ),
    "learned_public_source": PredicateDefinition(
        name="learned_public_source",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.TIME_BOUND,
        default_ttl_seconds=2_592_000,
        render_template="The system learned this from a public source: {value}.",
    ),
    "known_public_profile": PredicateDefinition(
        name="known_public_profile",
        cardinality=PredicateCardinality.MANY,
        temporal_mode=TemporalMode.TIME_BOUND,
        default_ttl_seconds=2_592_000,
        render_template="A public profile result was found: {value}.",
    ),
}


def get_predicate_definition(predicate: str) -> PredicateDefinition | None:
    return PREDICATE_REGISTRY.get(predicate)
