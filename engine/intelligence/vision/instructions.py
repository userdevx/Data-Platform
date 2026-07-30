from __future__ import annotations

from engine.intelligence.vision.models import (
    VisualAnalysisRequest,
)


def build_visual_instruction(
    request: VisualAnalysisRequest,
) -> str:
    query = " ".join(
        request.query.split()
    ).strip()

    if not query:
        raise ValueError(
            "A visual-analysis query is required."
        )

    requested_outputs = tuple(
        " ".join(value.split()).strip()
        for value in request.requested_outputs
        if value.strip()
    )

    output_text = (
        "\n".join(
            f"- {value}"
            for value in requested_outputs
        )
        if requested_outputs
        else (
            "- Determine the relevant visible evidence "
            "from the user query."
        )
    )

    return f"""
Analyze the supplied media only in relation to the user query.

User query:
{query}

Media mode:
{request.media_mode}

Requested outputs:
{output_text}

Return only observations supported by the supplied media.

Requirements:
- Generate relevant entity labels dynamically at runtime.
- Generate visible attributes dynamically at runtime.
- Generate relevant relations, states, or actions dynamically.
- Preserve entity references throughout the response.
- Transcribe visible text only when it is legible.
- Preserve ambiguity and uncertainty.
- Distinguish direct visibility from inference.
- Do not use a predefined visual taxonomy.
- Do not add information from model memory.
- Do not infer hidden intent, history, identity, or causation.
- Do not identify a real person from facial appearance.
- Do not present one frame as proof of repeated motion.
- Return structured data matching the required schema.
""".strip()
