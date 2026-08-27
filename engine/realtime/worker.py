from __future__ import annotations

from threading import Event
from typing import Any

from engine.realtime.ingestion import (
    RealTimeIngestionService,
)
from engine.realtime.source import (
    RealTimeSource,
)


class RealTimeCollectionWorker:
    """
    Repeatedly collect truthful observations from a
    RealTimeSource and persist them through the existing
    RealTimeIngestionService.

    The worker supports bounded execution for tests and
    controlled runs, plus continuous execution when no
    iteration limit is supplied.
    """

    def __init__(
        self,
        *,
        source: RealTimeSource,
        ingestion_service: (
            RealTimeIngestionService | None
        ) = None,
        interval_seconds: float = 30.0,
        max_consecutive_failures: int = 5,
    ) -> None:
        if not isinstance(
            source,
            RealTimeSource,
        ):
            raise TypeError(
                "source must implement RealTimeSource."
            )

        if not isinstance(
            interval_seconds,
            (int, float),
        ):
            raise TypeError(
                "interval_seconds must be numeric."
            )

        if interval_seconds < 0:
            raise ValueError(
                "interval_seconds cannot be negative."
            )

        if not isinstance(
            max_consecutive_failures,
            int,
        ):
            raise TypeError(
                "max_consecutive_failures "
                "must be an integer."
            )

        if max_consecutive_failures < 1:
            raise ValueError(
                "max_consecutive_failures "
                "must be at least 1."
            )

        self.source = source

        self.ingestion_service = (
            ingestion_service
            if ingestion_service is not None
            else RealTimeIngestionService()
        )

        self.interval_seconds = float(
            interval_seconds
        )

        self.max_consecutive_failures = (
            max_consecutive_failures
        )

    def run_once(
        self,
    ) -> Any:
        return (
            self.ingestion_service
            .ingest_source(
                self.source
            )
        )

    def run(
        self,
        *,
        iterations: int | None = None,
        stop_event: Event | None = None,
    ) -> dict[str, Any]:
        if (
            iterations is not None
            and not isinstance(
                iterations,
                int,
            )
        ):
            raise TypeError(
                "iterations must be an integer "
                "or None."
            )

        if (
            iterations is not None
            and iterations < 1
        ):
            raise ValueError(
                "iterations must be at least 1."
            )

        if (
            stop_event is not None
            and not isinstance(
                stop_event,
                Event,
            )
        ):
            raise TypeError(
                "stop_event must be a "
                "threading.Event or None."
            )

        effective_stop_event = (
            stop_event
            if stop_event is not None
            else Event()
        )

        attempts = 0
        successes = 0
        failures = 0
        consecutive_failures = 0
        last_error: str | None = None

        while (
            iterations is None
            or attempts < iterations
        ):
            if effective_stop_event.is_set():
                break

            attempts += 1

            try:
                self.run_once()

            except Exception as exc:
                failures += 1
                consecutive_failures += 1
                last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                if (
                    consecutive_failures
                    >= self.max_consecutive_failures
                ):
                    raise RuntimeError(
                        "Real-time collection stopped "
                        "after reaching the maximum "
                        "consecutive failure count."
                    ) from exc

            else:
                successes += 1
                consecutive_failures = 0
                last_error = None

            if (
                iterations is not None
                and attempts >= iterations
            ):
                break

            if effective_stop_event.wait(
                self.interval_seconds
            ):
                break

        return {
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "consecutive_failures": (
                consecutive_failures
            ),
            "last_error": last_error,
            "stopped": (
                effective_stop_event.is_set()
            ),
        }
