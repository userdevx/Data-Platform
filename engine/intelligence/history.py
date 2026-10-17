from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from engine.backend import get_backend
from engine.data_engine.record_writer import (
    DataEngineRecordWriter,
)
from engine.intelligence.models import (
    IntelligenceRequest,
    IntelligenceResponse,
)
from engine.query import QueryService


class IntelligenceHistoryWriter:
    """
    Data Engine-backed conversation history.

    This component preserves the existing Intelligence
    history integration point, but the Data Engine is now
    the source of truth for normal inquiry/response history.

    Conversation records use the canonical Data Platform
    envelope:

        source
        category
        data_type
        value
        unit
    """

    CATEGORY = "conversation"

    USER_INQUIRY = "user_inquiry"

    INTELLIGENCE_RESPONSE = (
        "intelligence_response"
    )

    def __init__(
        self,
        root: Path,
        *,
        query_service: QueryService | None = None,
    ) -> None:
        self.root = root

        self.query_service = (
            query_service
            if query_service is not None
            else QueryService(
                get_backend()
            )
        )

        self.writer = (
            DataEngineRecordWriter(
                query_service=(
                    self.query_service
                )
            )
        )

    @staticmethod
    def _conversation_id(
        request: IntelligenceRequest,
    ) -> str:
        value = request.metadata.get(
            "conversation_id",
            "",
        )

        clean = str(
            value
        ).strip()

        return (
            clean
            or "local_conversation"
        )

    @staticmethod
    def _safe_request_metadata(
        request: IntelligenceRequest,
    ) -> dict[str, Any]:
        metadata = dict(
            request.metadata
        )

        # Retrieval material must not recursively
        # become part of later stored conversation.
        metadata.pop(
            "conversation_context",
            None,
        )

        metadata.pop(
            "conversation_retrieval",
            None,
        )

        return metadata

    def write_inquiry(
        self,
        request: IntelligenceRequest,
    ) -> dict[str, Any]:
        conversation_id = (
            self._conversation_id(
                request
            )
        )

        return self.writer.write(
            source=request.source,
            category=self.CATEGORY,
            data_type=self.USER_INQUIRY,
            value={
                "request_id": (
                    request.request_id
                ),
                "conversation_id": (
                    conversation_id
                ),
                "created_at": (
                    request.created_at
                ),
                "inquiry": (
                    request.question
                ),
                "normalized_inquiry": (
                    request
                    .normalized_question
                ),
                "metadata": (
                    self
                    ._safe_request_metadata(
                        request
                    )
                ),
            },
            unit="record",
        )

    def write_response(
        self,
        request: IntelligenceRequest,
        response: IntelligenceResponse,
    ) -> dict[str, Any]:
        conversation_id = (
            self._conversation_id(
                request
            )
        )

        return self.writer.write(
            source="intelligence_runtime",
            category=self.CATEGORY,
            data_type=(
                self
                .INTELLIGENCE_RESPONSE
            ),
            value={
                "response_id": (
                    response.response_id
                ),
                "request_id": (
                    response.request_id
                ),
                "conversation_id": (
                    conversation_id
                ),
                "created_at": (
                    response.created_at
                ),
                "instance_id": (
                    response.instance_id
                ),
                "ability": (
                    response.ability
                ),
                "capability": (
                    response.capability
                ),
                "response_source": (
                    response.source
                ),
                "status": (
                    response.status
                ),
                "answer": (
                    response.answer
                ),
                "data": dict(
                    response.data
                ),
                "errors": list(
                    response.errors
                ),
            },
            unit="record",
        )

    def write(
        self,
        request: IntelligenceRequest,
        response: IntelligenceResponse,
    ) -> None:
        """
        Compatibility entry point.

        New production execution writes the inquiry
        before routing and the response after execution.
        """

        self.write_inquiry(
            request
        )

        self.write_response(
            request,
            response,
        )

    @staticmethod
    def _tokens(
        value: str,
    ) -> frozenset[str]:
        return frozenset(
            token
            for token in re.findall(
                r"[a-z0-9]+",
                str(value).casefold(),
            )
            if len(token) > 1
        )

    @staticmethod
    def _record_text(
        record: dict[str, Any],
    ) -> str:
        value = record.get(
            "value",
            {},
        )

        if not isinstance(
            value,
            dict,
        ):
            return ""

        data_type = str(
            record.get(
                "data_type",
                "",
            )
        )

        if (
            data_type
            == IntelligenceHistoryWriter
            .USER_INQUIRY
        ):
            return str(
                value.get(
                    "inquiry",
                    "",
                )
            )

        if (
            data_type
            == IntelligenceHistoryWriter
            .INTELLIGENCE_RESPONSE
        ):
            return str(
                value.get(
                    "answer",
                    "",
                )
            )

        return ""

    @staticmethod
    def _record_conversation_id(
        record: dict[str, Any],
    ) -> str:
        value = record.get(
            "value",
            {},
        )

        if not isinstance(
            value,
            dict,
        ):
            return ""

        return str(
            value.get(
                "conversation_id",
                "",
            )
        ).strip()

    @staticmethod
    def _record_request_id(
        record: dict[str, Any],
    ) -> str:
        value = record.get(
            "value",
            {},
        )

        if not isinstance(
            value,
            dict,
        ):
            return ""

        return str(
            value.get(
                "request_id",
                "",
            )
        ).strip()

    @staticmethod
    def _record_id(
        record: dict[str, Any],
    ) -> int:
        value = record.get(
            "id"
        )

        if isinstance(
            value,
            int,
        ):
            return value

        return 0

    def conversation_records(
        self,
    ) -> list[dict[str, Any]]:
        records = (
            self.query_service
            .get_all_records()
        )

        results = [
            record
            for record in records
            if (
                isinstance(
                    record,
                    dict,
                )
                and record.get(
                    "category"
                )
                == self.CATEGORY
                and record.get(
                    "data_type"
                )
                in {
                    self.USER_INQUIRY,
                    self.INTELLIGENCE_RESPONSE,
                }
            )
        ]

        return sorted(
            results,
            key=self._record_id,
        )

    def build_context(
        self,
        request: IntelligenceRequest,
        *,
        recent_limit: int = 6,
        relevant_limit: int = 6,
        max_characters: int = 6000,
        minimum_relevance: float = 0.35,
    ) -> dict[str, Any]:
        records = [
            record
            for record
            in self.conversation_records()
            if (
                self._record_request_id(
                    record
                )
                != request.request_id
            )
        ]

        if not records:
            return {
                "context": "",
                "selected_record_ids": [],
                "selected_record_count": 0,
                "available_record_count": 0,
                "same_conversation_count": 0,
                "conversation_id": (
                    self._conversation_id(
                        request
                    )
                ),
            }

        conversation_id = (
            self._conversation_id(
                request
            )
        )

        same_conversation = [
            record
            for record in records
            if (
                self
                ._record_conversation_id(
                    record
                )
                == conversation_id
            )
        ]

        # Preserve immediate continuity first.
        recent_source = (
            same_conversation
            if same_conversation
            else records
        )

        recent = (
            recent_source[
                -recent_limit:
            ]
        )

        query_tokens = (
            self._tokens(
                request.question
            )
        )

        scored: list[
            tuple[
                float,
                int,
                dict[str, Any],
            ]
        ] = []

        total = max(
            1,
            len(records),
        )

        for position, record in enumerate(
            records,
            start=1,
        ):
            text = (
                self._record_text(
                    record
                )
            )

            record_tokens = (
                self._tokens(
                    text
                )
            )

            if (
                query_tokens
                and record_tokens
            ):
                intersection = len(
                    query_tokens
                    & record_tokens
                )

                union = len(
                    query_tokens
                    | record_tokens
                )

                lexical = (
                    intersection
                    / union
                    if union
                    else 0.0
                )

            else:
                lexical = 0.0

            recency = (
                position
                / total
            )

            same_conversation_boost = (
                0.20
                if (
                    self
                    ._record_conversation_id(
                        record
                    )
                    == conversation_id
                )
                else 0.0
            )

            score = (
                lexical
                + (
                    recency
                    * 0.15
                )
                + same_conversation_boost
            )

            scored.append(
                (
                    score,
                    self._record_id(
                        record
                    ),
                    record,
                )
            )

        scored.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        # A same-conversation record scores at least 0.20 from the
        # boost alone, so without a floor an unrelated turn qualifies
        # on membership rather than relevance. The floor applies only
        # to the scored set: `recent` is immediate continuity and is
        # admitted regardless.
        qualified = [
            item
            for item in scored
            if item[0] >= minimum_relevance
        ]

        # Value per token, not raw score. A short fact and a long
        # transcript at equal relevance are not equally worth the
        # window: prefill is real wall time at CPU inference speed.
        qualified.sort(
            key=lambda item: (
                item[0]
                / max(
                    1,
                    len(
                        self._record_text(
                            item[2]
                        )
                    ),
                ),
                item[0],
                item[1],
            ),
            reverse=True,
        )

        relevant = [
            item[2]
            for item
            in qualified[
                :relevant_limit
            ]
        ]

        rejected_below_relevance = (
            len(scored)
            - len(qualified)
        )

        selected_by_id: dict[
            int,
            dict[str, Any],
        ] = {}

        for record in (
            recent
            + relevant
        ):
            selected_by_id[
                self._record_id(
                    record
                )
            ] = record

        selected = [
            selected_by_id[
                record_id
            ]
            for record_id
            in sorted(
                selected_by_id
            )
        ]

        lines = [
            "<conversation_context>"
        ]

        selected_ids: list[int] = []

        for record in selected:
            record_id = (
                self._record_id(
                    record
                )
            )

            text = (
                self._record_text(
                    record
                )
                .strip()
            )

            if not text:
                continue

            selected_ids.append(
                record_id
            )

            if (
                record.get(
                    "data_type"
                )
                == self.USER_INQUIRY
            ):
                role = "User"

            else:
                role = "Intelligence"

            lines.append(
                f"{role}: {text}"
            )

        lines.append(
            "</conversation_context>"
        )

        context = "\n".join(
            lines
        )

        if (
            len(context)
            > max_characters
        ):
            context = (
                context[
                    -max_characters:
                ]
            )

        return {
            "context": context,
            "selected_record_ids": (
                selected_ids
            ),
            "selected_record_count": (
                len(
                    selected_ids
                )
            ),
            "available_record_count": (
                len(records)
            ),
            "same_conversation_count": (
                len(
                    same_conversation
                )
            ),
            "conversation_id": (
                conversation_id
            ),
        }
