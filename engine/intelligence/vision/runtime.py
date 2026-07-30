from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from engine.intelligence.vision.analyzer import (
    VisualAnalyzer,
)
from engine.intelligence.vision.answer_renderer import (
    build_visual_answer,
)
from engine.intelligence.vision.config import (
    VisualConfiguration,
)
from engine.intelligence.vision.data_engine_adapter import (
    build_media_frame_record,
    build_visual_observation_record,
)
from engine.intelligence.vision.frame_sampler import (
    FrameSampler,
)
from engine.intelligence.vision.models import (
    MediaFrame,
    VisualAnalysisRequest,
    VisualRuntimeResult,
)
from engine.intelligence.vision.providers.unavailable import (
    VisualAnalyzerUnavailableError,
)
from engine.intelligence.vision.validator import (
    validate_media_frame,
    validate_visual_observation,
)


RecordWriter = Callable[[dict], None]


class VisualRuntime:
    def __init__(
        self,
        *,
        analyzer: VisualAnalyzer,
        configuration: VisualConfiguration,
        record_writer: RecordWriter,
    ) -> None:
        self.analyzer = analyzer
        self.configuration = configuration
        self.record_writer = record_writer
        self.sampler = FrameSampler(
            minimum_interval_ms=(
                configuration.sampling.minimum_interval_ms
            ),
            maximum_pending_frames=(
                configuration.sampling.maximum_pending_frames
            ),
        )

    def process_frame(
        self,
        *,
        frame: MediaFrame,
        query: str,
        media_mode: str,
        request_id: str | None = None,
        source_reference: str | None = None,
    ) -> VisualRuntimeResult:
        if not self.configuration.enabled:
            return VisualRuntimeResult(
                status="unavailable",
                answer=(
                    "Visual analysis is disabled by the "
                    "active configuration. No visual claims "
                    "were generated."
                ),
            )

        clean_query = " ".join(
            query.split()
        ).strip()

        if not clean_query:
            return VisualRuntimeResult(
                status="rejected",
                answer=(
                    "A visual-analysis question is required."
                ),
                errors=("query is required",),
            )

        clean_media_mode = media_mode.strip()

        if clean_media_mode not in {
            "single_image",
            "frame_sequence",
        }:
            return VisualRuntimeResult(
                status="rejected",
                answer=(
                    "The supplied media mode is not supported."
                ),
                errors=("invalid media_mode",),
            )

        frame_errors = validate_media_frame(frame)

        if frame_errors:
            return VisualRuntimeResult(
                status="invalid_media",
                answer=(
                    "The media frame could not be validated. "
                    "No visual claims were generated."
                ),
                errors=tuple(frame_errors),
            )

        sampling = self.sampler.should_analyze(
            frame
        )

        if not sampling.analyze:
            return VisualRuntimeResult(
                status="skipped",
                answer="",
                errors=(sampling.reason,),
            )

        request = VisualAnalysisRequest(
            request_id=request_id or uuid4().hex,
            query=clean_query,
            media_source_id=frame.source_id,
            media_mode=clean_media_mode,
            created_at=datetime.now(UTC).isoformat(),
            sequence_id=(
                frame.sequence_id
                if clean_media_mode == "frame_sequence"
                else None
            ),
            source_reference=source_reference,
        )

        self.sampler.begin_pending()

        try:
            observation = self.analyzer.analyze(
                request=request,
                frame=frame,
            )
        except VisualAnalyzerUnavailableError as error:
            return VisualRuntimeResult(
                status="unavailable",
                answer=(
                    "Visual analysis could not run because "
                    "no visual provider is configured. "
                    "No visual claims were generated."
                ),
                errors=(str(error),),
            )
        except Exception as error:
            return VisualRuntimeResult(
                status="provider_error",
                answer=(
                    "The visual provider could not complete "
                    "the analysis. No visual claims were generated."
                ),
                errors=(str(error),),
            )
        finally:
            self.sampler.end_pending()

        observation_errors = (
            validate_visual_observation(
                observation,
                minimum_entity_confidence=(
                    self.configuration.validation
                    .minimum_entity_confidence
                ),
                minimum_relation_confidence=(
                    self.configuration.validation
                    .minimum_relation_confidence
                ),
            )
        )

        if observation_errors:
            return VisualRuntimeResult(
                status="invalid_observation",
                answer=(
                    "The visual provider returned evidence "
                    "that failed validation. No visual conclusion "
                    "was generated."
                ),
                observation=observation,
                errors=tuple(observation_errors),
            )

        records: list[dict] = []

        if self.configuration.storage.store_raw_frames:
            frame_record = build_media_frame_record(
                frame
            )
            self.record_writer(frame_record)
            records.append(frame_record)

        if (
            self.configuration.storage
            .store_validated_observations
        ):
            observation_record = (
                build_visual_observation_record(
                    observation
                )
            )
            self.record_writer(
                observation_record
            )
            records.append(
                observation_record
            )

        return VisualRuntimeResult(
            status="success",
            answer=build_visual_answer(
                observation
            ),
            observation=observation,
            records=tuple(records),
        )
