from __future__ import annotations

import threading


class SandboxCancelled(RuntimeError):
    pass


class CancellationToken:
    """Thread-safe, one-way cancellation signal for a sandbox run."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._reason: str | None = None

    def cancel(self, reason: str = "cancelled") -> None:
        with self._lock:
            if self._reason is None:
                self._reason = reason

        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        return self._reason

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise SandboxCancelled(self._reason or "cancelled")
