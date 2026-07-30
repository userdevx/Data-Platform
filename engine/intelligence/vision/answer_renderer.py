from __future__ import annotations

from engine.intelligence.vision.models import (
    TemporalObservation,
    VisualObservation,
    VisualStateRecord,
)
from engine.intelligence.vision.validator import (
    validate_temporal_observation,
    validate_visual_observation,
    validate_visual_state,
)


def build_visual_answer(
    observation: VisualObservation,
) -> str:
    errors = validate_visual_observation(
        observation
    )

    if errors:
        return (
            "The visual evidence could not be validated, "
            "so no visual conclusion was generated."
        )

    lines = [
        observation.scene_description.strip(),
    ]

    if observation.visible_text:
        lines.extend(
            [
                "",
                "Legible visible text:",
                *[
                    f"- {value}"
                    for value in observation.visible_text
                ],
            ]
        )

    if observation.uncertainty:
        lines.extend(
            [
                "",
                "Uncertain details:",
                *[
                    f"- {value}"
                    for value in observation.uncertainty
                ],
            ]
        )

    return "\n".join(lines)


def build_temporal_answer(
    observation: TemporalObservation,
) -> str:
    errors = validate_temporal_observation(
        observation
    )

    if errors:
        return (
            "The temporal visual evidence could not be "
            "validated, so no temporal conclusion was generated."
        )

    lines = [
        observation.description.strip(),
    ]

    if observation.uncertainty:
        lines.extend(
            [
                "",
                "Uncertain details:",
                *[
                    f"- {value}"
                    for value in observation.uncertainty
                ],
            ]
        )

    return "\n".join(lines)


def build_state_answer(
    state: VisualStateRecord,
) -> str:
    errors = validate_visual_state(state)

    if errors:
        return (
            "The current visual state could not be "
            "validated, so no live conclusion was generated."
        )

    lines = [
        state.description.strip(),
    ]

    if state.uncertainty:
        lines.extend(
            [
                "",
                "Uncertain details:",
                *[
                    f"- {value}"
                    for value in state.uncertainty
                ],
            ]
        )

    return "\n".join(lines)
