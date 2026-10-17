from __future__ import annotations

from engine.intelligence.history import (
    IntelligenceHistoryWriter,
)
from engine.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResponse,
)
from engine.query import QueryService
from engine.storage.json_backend import (
    LocalJsonStorageBackend,
)


def build_history(
    tmp_path,
):
    backend = (
        LocalJsonStorageBackend(
            str(
                tmp_path
                / "records.json"
            )
        )
    )

    query_service = (
        QueryService(
            backend
        )
    )

    return (
        IntelligenceHistoryWriter(
            root=tmp_path,
            query_service=(
                query_service
            ),
        ),
        query_service,
    )


def response_for(
    request,
    answer,
):
    return (
        IntelligenceResponse.create(
            request=request,
            instance_id="test",
            instance_name="test",
            instance_role="test",
            ability="model_reasoning",
            capability="model_reasoning",
            source="model_provider",
            status="success",
            answer=answer,
            data={},
            errors=[],
        )
    )


def test_inquiry_and_response_use_canonical_data_engine_records(
    tmp_path,
):
    (
        history,
        query_service,
    ) = build_history(
        tmp_path
    )

    request = (
        IntelligenceRequest.create(
            question=(
                "Explain parrots."
            ),
            source=(
                "application_interface"
            ),
            metadata={
                "conversation_id": (
                    "conversation-a"
                )
            },
        )
    )

    history.write_inquiry(
        request
    )

    history.write_response(
        request,
        response_for(
            request,
            "Parrots are birds.",
        ),
    )

    records = (
        query_service
        .get_all_records()
    )

    conversation = [
        record
        for record in records
        if record.get(
            "category"
        )
        == "conversation"
    ]

    assert (
        len(conversation)
        == 2
    )

    assert (
        conversation[0][
            "source"
        ]
        == "application_interface"
    )

    assert (
        conversation[0][
            "data_type"
        ]
        == "user_inquiry"
    )

    assert (
        conversation[1][
            "source"
        ]
        == "intelligence_runtime"
    )

    assert (
        conversation[1][
            "data_type"
        ]
        == "intelligence_response"
    )

    for record in conversation:
        for field in (
            "source",
            "category",
            "data_type",
            "value",
            "unit",
        ):
            assert (
                field in record
            )


def test_prior_conversation_is_retrieved(
    tmp_path,
):
    history, _ = build_history(
        tmp_path
    )

    first = (
        IntelligenceRequest.create(
            question=(
                "Explain parrots."
            ),
            source=(
                "application_interface"
            ),
            metadata={
                "conversation_id": (
                    "conversation-a"
                )
            },
        )
    )

    history.write_inquiry(
        first
    )

    history.write_response(
        first,
        response_for(
            first,
            "Parrots can mimic sounds.",
        ),
    )

    followup = (
        IntelligenceRequest.create(
            question=(
                "What animal was I "
                "asking about?"
            ),
            source=(
                "application_interface"
            ),
            metadata={
                "conversation_id": (
                    "conversation-a"
                )
            },
        )
    )

    result = (
        history.build_context(
            followup
        )
    )

    assert (
        result[
            "selected_record_count"
        ]
        >= 2
    )

    assert (
        "parrots"
        in result[
            "context"
        ].lower()
    )


def test_new_runtime_instance_reads_persisted_conversation(
    tmp_path,
):
    history, query_service = (
        build_history(
            tmp_path
        )
    )

    first = (
        IntelligenceRequest.create(
            question=(
                "Explain copper."
            ),
            source=(
                "application_interface"
            ),
            metadata={
                "conversation_id": (
                    "conversation-b"
                )
            },
        )
    )

    history.write_inquiry(
        first
    )

    history.write_response(
        first,
        response_for(
            first,
            "Copper conducts electricity.",
        ),
    )

    restarted = (
        IntelligenceHistoryWriter(
            root=tmp_path,
            query_service=(
                query_service
            ),
        )
    )

    followup = (
        IntelligenceRequest.create(
            question=(
                "What material did I "
                "ask about?"
            ),
            source=(
                "application_interface"
            ),
            metadata={
                "conversation_id": (
                    "conversation-b"
                )
            },
        )
    )

    result = (
        restarted.build_context(
            followup
        )
    )

    assert (
        "copper"
        in result[
            "context"
        ].lower()
    )
