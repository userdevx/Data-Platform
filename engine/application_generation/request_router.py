from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from engine.application_generation.template_catalog import (
    ApplicationTemplateCatalog,
)


class ApplicationRoutingError(RuntimeError):
    pass


@dataclass(frozen=True)
class RoutingDecision:
    template_id: str
    matched_signals: tuple[str, ...]
    candidates: tuple[str, ...]
    strategy: str = "deterministic-manifest-v1"


class ApplicationRequestRouter:
    def __init__(
        self,
        *,
        catalog: ApplicationTemplateCatalog,
        routes_path: Path,
    ) -> None:
        self.catalog = catalog
        self.routes_path = Path(routes_path)

    @staticmethod
    def _matches(request: str, signal: str) -> bool:
        expression = (
            r"(?<!\w)"
            + re.escape(signal).replace(r"\ ", r"\s+")
            + r"(?!\w)"
        )
        return re.search(expression, request, re.I) is not None

    def route(self, request: str) -> RoutingDecision:
        if not isinstance(request, str) or not request.strip():
            raise ApplicationRoutingError(
                "Describe what you want to build."
            )

        if len(request) > 20000:
            raise ApplicationRoutingError(
                "Application request exceeds the supported limit."
            )

        try:
            document = json.loads(
                self.routes_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise ApplicationRoutingError(
                "Application routing configuration unavailable."
            ) from exc

        if not isinstance(document, dict) or (
            document.get("schema_version") != 1
        ):
            raise ApplicationRoutingError(
                "Unsupported routing configuration."
            )

        routes = document.get("routes")
        if not isinstance(routes, list) or not routes:
            raise ApplicationRoutingError(
                "No application routes are configured."
            )

        registered = self.catalog.discover()
        matches: dict[str, tuple[str, ...]] = {}
        configured = set()

        for route in routes:
            if not isinstance(route, dict):
                raise ApplicationRoutingError(
                    "Invalid application route."
                )

            template_id = route.get("template_id")
            signals = route.get("signals")

            if (
                not isinstance(template_id, str)
                or template_id not in registered
                or template_id in configured
                or not isinstance(signals, list)
                or not signals
                or any(
                    not isinstance(signal, str)
                    or not signal.strip()
                    for signal in signals
                )
            ):
                raise ApplicationRoutingError(
                    "Invalid or unregistered application route."
                )

            configured.add(template_id)

            matched = tuple(
                signal
                for signal in signals
                if self._matches(request, signal)
            )

            if matched:
                matches[template_id] = matched

        # Existing verified Builder environment supports Linux.
        if re.search(
            r"(?<!\w)(android|iphone|ipad|ios|windows|macos)"
            r"(?!\w)",
            request,
            re.I,
        ):
            raise ApplicationRoutingError(
                "Requested target platform is not verified "
                "for this Builder."
            )

        if not matches:
            raise ApplicationRoutingError(
                "Application requirements do not identify "
                "a supported generation capability."
            )

        if len(matches) != 1:
            raise ApplicationRoutingError(
                "Application requirements match multiple "
                "capabilities. Specify the intended target."
            )

        template_id, signals = next(iter(matches.items()))
        definition = registered[template_id]

        if "linux" not in definition.platforms:
            raise ApplicationRoutingError(
                "Selected template is not enabled for Linux."
            )

        return RoutingDecision(
            template_id=template_id,
            matched_signals=signals,
            candidates=tuple(sorted(matches)),
        )
