from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from services.visual_model.errors import (
    VisualModelBackendRegistrationError,
)
from services.visual_model.providers.private_runtime import (
    PrivateVisualBackend,
)


PrivateVisualBackendFactory = Callable[
    [],
    PrivateVisualBackend,
]


def _normalize_backend_name(
    value: str,
) -> str:
    return value.strip().lower()


@dataclass
class PrivateVisualBackendRegistry:
    _factories: dict[
        str,
        PrivateVisualBackendFactory,
    ] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def register(
        self,
        *,
        backend_name: str,
        factory: PrivateVisualBackendFactory,
    ) -> None:
        normalized_name = _normalize_backend_name(
            backend_name
        )

        if not normalized_name:
            raise VisualModelBackendRegistrationError(
                "backend_name is required."
            )

        if not callable(factory):
            raise VisualModelBackendRegistrationError(
                "backend factory must be callable."
            )

        if normalized_name in self._factories:
            raise VisualModelBackendRegistrationError(
                "The visual backend is already registered."
            )

        self._factories[
            normalized_name
        ] = factory

    def unregister(
        self,
        backend_name: str,
    ) -> bool:
        normalized_name = _normalize_backend_name(
            backend_name
        )

        return (
            self._factories.pop(
                normalized_name,
                None,
            )
            is not None
        )

    def contains(
        self,
        backend_name: str,
    ) -> bool:
        return (
            _normalize_backend_name(
                backend_name
            )
            in self._factories
        )

    def registered_names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(self._factories)
        )

    def create(
        self,
        backend_name: str,
    ) -> PrivateVisualBackend:
        normalized_name = _normalize_backend_name(
            backend_name
        )

        if not normalized_name:
            raise VisualModelBackendRegistrationError(
                "backend_name is required."
            )

        factory = self._factories.get(
            normalized_name
        )

        if factory is None:
            raise VisualModelBackendRegistrationError(
                "The configured visual backend "
                "is not registered."
            )

        try:
            backend = factory()
        except VisualModelBackendRegistrationError:
            raise
        except Exception as error:
            raise VisualModelBackendRegistrationError(
                "The visual backend factory failed."
            ) from error

        if not isinstance(
            backend,
            PrivateVisualBackend,
        ):
            raise VisualModelBackendRegistrationError(
                "The backend factory returned an "
                "incompatible object."
            )

        return backend
