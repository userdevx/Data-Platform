from __future__ import annotations

import argparse
import os

from huggingface_hub import InferenceClient


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a Hugging Face sentence-similarity model "
            "using real runtime input."
        )
    )

    parser.add_argument(
        "--model-id",
        default=os.environ.get(
            "HF_SIMILARITY_MODEL_ID",
            "",
        ).strip(),
        help=(
            "Hugging Face model ID. "
            "Defaults to HF_SIMILARITY_MODEL_ID."
        ),
    )

    parser.add_argument(
        "--source",
        required=True,
        help="Source text used for comparison.",
    )

    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        help=(
            "Candidate text to compare against the source. "
            "Use this option multiple times."
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    token = os.environ.get(
        "HF_TOKEN",
        "",
    ).strip()

    model_id = arguments.model_id.strip()
    source_text = arguments.source.strip()

    candidate_texts = [
        candidate.strip()
        for candidate in arguments.candidate
        if candidate.strip()
    ]

    if not token:
        raise SystemExit(
            "HF_TOKEN is missing."
        )

    if not model_id:
        raise SystemExit(
            "HF_SIMILARITY_MODEL_ID or --model-id is required."
        )

    if not source_text:
        raise SystemExit(
            "Source text is missing."
        )

    if not candidate_texts:
        raise SystemExit(
            "At least one candidate text is required."
        )

    client = InferenceClient(
        provider="hf-inference",
        api_key=token,
    )

    print("Model ID:", model_id)
    print("Task: sentence-similarity")
    print("Source:", source_text)
    print("Candidates:", len(candidate_texts))
    print()
    print("Sending request...")

    result = client.sentence_similarity(
        source_text,
        other_sentences=candidate_texts,
        model=model_id,
    )

    print()
    print("Request: success")

    ranked_results = sorted(
        zip(candidate_texts, result),
        key=lambda item: item[1],
        reverse=True,
    )

    for candidate, score in ranked_results:
        print(
            f"{float(score):.6f} | {candidate}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
