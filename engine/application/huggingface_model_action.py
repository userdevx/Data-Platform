from __future__ import annotations

from dataclasses import (
    asdict,
    is_dataclass,
)
from math import sqrt
from typing import Any

from huggingface_hub import InferenceClient

from services.visual_model.provider_configuration import (
    VisualProviderConfiguration,
)
from services.visual_model.provider_contracts import (
    VisualModelDescriptor,
)
from services.visual_model.provider_errors import (
    VisualProviderResponseError,
    VisualProviderUnavailableError,
)
from services.visual_model.provider_http import (
    resolve_credential,
)


HUGGING_FACE_CAPABILITIES = frozenset(
    {
        "text_input",
        "feature_extraction",
        "semantic_similarity",
        "text_classification",
    }
)


def is_hugging_face_provider(
    provider: VisualProviderConfiguration,
) -> bool:
    adapter_type = (
        provider.adapter_type
        .strip()
        .lower()
    )

    credential_reference = (
        provider.credential_reference
        .strip()
    )

    return (
        adapter_type.startswith(
            "huggingface"
        )
        or credential_reference
        == "HF_TOKEN"
    )


def _json_safe(
    value: Any,
) -> Any:
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if is_dataclass(value):
        return _json_safe(
            asdict(value)
        )

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _json_safe(item)
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    to_list = getattr(
        value,
        "tolist",
        None,
    )

    if callable(to_list):
        return _json_safe(
            to_list()
        )

    dictionary = getattr(
        value,
        "__dict__",
        None,
    )

    if isinstance(
        dictionary,
        dict,
    ):
        return _json_safe(
            dictionary
        )

    return str(value)


def _sentence_vector(
    value: Any,
) -> tuple[float, ...]:
    data = _json_safe(value)

    while (
        isinstance(data, list)
        and len(data) == 1
        and isinstance(data[0], list)
        and data[0]
        and isinstance(
            data[0][0],
            list,
        )
    ):
        data = data[0]

    if (
        isinstance(data, list)
        and data
        and all(
            isinstance(
                item,
                (
                    int,
                    float,
                ),
            )
            for item in data
        )
    ):
        return tuple(
            float(item)
            for item in data
        )

    if (
        not isinstance(data, list)
        or not data
    ):
        raise VisualProviderResponseError(
            "The embedding response is empty."
        )

    rows = []

    for row in data:
        if (
            not isinstance(row, list)
            or not row
            or not all(
                isinstance(
                    item,
                    (
                        int,
                        float,
                    ),
                )
                for item in row
            )
        ):
            raise VisualProviderResponseError(
                "The embedding response "
                "has an unsupported shape."
            )

        rows.append(
            tuple(
                float(item)
                for item in row
            )
        )

    width = len(rows[0])

    if any(
        len(row) != width
        for row in rows
    ):
        raise VisualProviderResponseError(
            "Embedding rows must have "
            "equal dimensions."
        )

    return tuple(
        sum(
            row[index]
            for row in rows
        )
        / len(rows)
        for index in range(width)
    )


def _cosine_similarity(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    if (
        not left
        or not right
        or len(left) != len(right)
    ):
        raise VisualProviderResponseError(
            "Embeddings must have matching "
            "dimensions."
        )

    numerator = sum(
        left_value * right_value
        for left_value, right_value
        in zip(
            left,
            right,
            strict=True,
        )
    )

    left_norm = sqrt(
        sum(
            value * value
            for value in left
        )
    )

    right_norm = sqrt(
        sum(
            value * value
            for value in right
        )
    )

    denominator = (
        left_norm
        * right_norm
    )

    if denominator == 0:
        raise VisualProviderResponseError(
            "Cannot calculate similarity "
            "for a zero-length embedding."
        )

    return numerator / denominator


def _comparison_inputs(
    arguments: dict[str, Any],
) -> tuple[str, ...]:
    multiple = arguments.get(
        "comparison_texts"
    )

    if isinstance(multiple, list):
        values = tuple(
            str(item).strip()
            for item in multiple
            if str(item).strip()
        )

        if values:
            return values

    single = str(
        arguments.get(
            "comparison_text",
            "",
        )
    ).strip()

    if single:
        return (single,)

    raise ValueError(
        "semantic_similarity requires "
        "comparison_text or comparison_texts."
    )


def _chat_answer(
    response: Any,
) -> str:
    choices = getattr(
        response,
        "choices",
        None,
    )

    if not choices:
        raise VisualProviderResponseError(
            "Hugging Face returned no "
            "chat choices."
        )

    message = getattr(
        choices[0],
        "message",
        None,
    )

    content = getattr(
        message,
        "content",
        "",
    )

    if not isinstance(
        content,
        str,
    ) or not content.strip():
        raise VisualProviderResponseError(
            "Hugging Face returned no "
            "response text."
        )

    return content.strip()


def process_hugging_face_model_request(
    *,
    provider: VisualProviderConfiguration,
    descriptor: VisualModelDescriptor,
    capability: str,
    question: str,
    arguments: dict[str, Any],
) -> tuple[
    str,
    dict[str, Any],
    list[dict[str, Any]],
]:
    clean_capability = (
        capability.strip().lower()
    )

    if (
        clean_capability
        not in HUGGING_FACE_CAPABILITIES
    ):
        raise VisualProviderUnavailableError(
            "The selected Hugging Face "
            "adapter does not implement "
            f"the capability: {clean_capability}"
        )

    credential = resolve_credential(
        provider.credential_reference
    )

    inference_provider = str(
        descriptor.metadata.get(
            "inference_provider",
            "auto",
        )
    ).strip() or "auto"

    client = InferenceClient(
        provider=inference_provider,
        api_key=credential,
        timeout=provider.timeout_seconds,
    )

    model_id = descriptor.model_id

    if clean_capability == "text_input":
        response = client.chat_completion(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": question,
                }
            ],
            max_tokens=1024,
        )

        return (
            _chat_answer(response),
            {
                "execution": (
                    "huggingface_chat_completion"
                ),
                "inference_provider": (
                    inference_provider
                ),
            },
            [],
        )

    if (
        clean_capability
        == "feature_extraction"
    ):
        raw_result = (
            client.feature_extraction(
                question,
                model=model_id,
            )
        )

        vector = _sentence_vector(
            raw_result
        )

        return (
            "Feature extraction completed.",
            {
                "execution": (
                    "huggingface_feature_extraction"
                ),
                "inference_provider": (
                    inference_provider
                ),
                "vector_dimensions": (
                    len(vector)
                ),
                "embedding": list(vector),
            },
            [],
        )

    if (
        clean_capability
        == "semantic_similarity"
    ):
        comparisons = (
            _comparison_inputs(
                arguments
            )
        )

        source_embedding = (
            _sentence_vector(
                client.feature_extraction(
                    question,
                    model=model_id,
                )
            )
        )

        results = []

        for index, comparison in enumerate(
            comparisons
        ):
            comparison_embedding = (
                _sentence_vector(
                    client.feature_extraction(
                        comparison,
                        model=model_id,
                    )
                )
            )

            score = _cosine_similarity(
                source_embedding,
                comparison_embedding,
            )

            results.append(
                {
                    "comparison_index": (
                        index
                    ),
                    "score": score,
                }
            )

        if len(results) == 1:
            answer = (
                "Semantic similarity: "
                f"{results[0]['score']:.4f}"
            )
        else:
            answer = (
                "Semantic similarity was "
                f"calculated for "
                f"{len(results)} inputs."
            )

        return (
            answer,
            {
                "execution": (
                    "huggingface_semantic_similarity"
                ),
                "inference_provider": (
                    inference_provider
                ),
                "scores": results,
            },
            results,
        )

    if (
        clean_capability
        == "text_classification"
    ):
        raw_result = (
            client.text_classification(
                question,
                model=model_id,
            )
        )

        structured_result = (
            _json_safe(
                raw_result
            )
        )

        answer = (
            "Text classification completed."
        )

        if (
            isinstance(
                structured_result,
                list,
            )
            and structured_result
            and isinstance(
                structured_result[0],
                dict,
            )
        ):
            label = str(
                structured_result[0].get(
                    "label",
                    "",
                )
            ).strip()

            score = (
                structured_result[0].get(
                    "score"
                )
            )

            if label:
                if isinstance(
                    score,
                    (
                        int,
                        float,
                    ),
                ):
                    answer = (
                        f"{label}: "
                        f"{float(score):.4f}"
                    )
                else:
                    answer = label

        return (
            answer,
            {
                "execution": (
                    "huggingface_text_classification"
                ),
                "inference_provider": (
                    inference_provider
                ),
                "classification": (
                    structured_result
                ),
            },
            (
                structured_result
                if isinstance(
                    structured_result,
                    list,
                )
                else []
            ),
        )

    raise VisualProviderUnavailableError(
        "No Hugging Face execution "
        "handler matched the capability."
    )
