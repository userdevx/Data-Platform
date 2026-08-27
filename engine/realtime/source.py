from __future__ import annotations

from abc import ABC, abstractmethod

from engine.realtime.models import (
    RealTimeObservation,
)


class RealTimeSource(ABC):
    """
    Contract for a real incoming information source.

    Implementations must return a truthful observation
    from the underlying source.

    Acquisition failures must raise an exception rather
    than generating substitute or fabricated values.
    """

    @abstractmethod
    def collect(
        self,
    ) -> RealTimeObservation:
        """
        Collect one real observation.

        Returns:
            RealTimeObservation:
                The observation acquired from the source.

        Raises:
            Exception:
                If the underlying source cannot be read.
        """
        raise NotImplementedError
