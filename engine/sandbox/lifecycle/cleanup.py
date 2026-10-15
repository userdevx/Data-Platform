from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass


CleanupAction = Callable[[], None]


class CleanupError(RuntimeError):
    """One or more cleanup actions failed.

    Every action still ran; ``failures`` lists each failed action's name
    and exception, in the order the actions ran.
    """

    def __init__(
        self,
        failures: list[tuple[str, BaseException]],
    ) -> None:
        self.failures = tuple(failures)

        detail = "; ".join(
            f"{name}: {type(exc).__name__}: {exc}"
            for name, exc in failures
        )

        super().__init__(
            f"{len(failures)} cleanup action(s) failed: {detail}"
        )


@dataclass(frozen=True, slots=True)
class CleanupReport:
    completed: tuple[str, ...]
    failed: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failed


class CleanupStack:
    """Last-in, first-out cleanup that always runs every action.

    A failing action never prevents the remaining actions from running.
    ``run()`` is idempotent: actions run at most once.
    """

    def __init__(self) -> None:
        self._actions: list[tuple[str, CleanupAction]] = []
        self._lock = threading.Lock()
        self._report: CleanupReport | None = None

    def add(
        self,
        action: CleanupAction,
        *,
        name: str | None = None,
    ) -> None:
        if not callable(action):
            raise TypeError("cleanup action must be callable")

        with self._lock:
            if self._report is not None:
                raise RuntimeError(
                    "cannot add a cleanup action after cleanup ran"
                )

            self._actions.append(
                (
                    name
                    or getattr(action, "__name__", None)
                    or repr(action),
                    action,
                )
            )

    @property
    def pending(self) -> tuple[str, ...]:
        with self._lock:
            if self._report is not None:
                return ()

            return tuple(name for name, _ in self._actions)

    @property
    def report(self) -> CleanupReport | None:
        return self._report

    def run(self) -> CleanupReport:
        with self._lock:
            if self._report is not None:
                return self._report

            actions = list(reversed(self._actions))
            self._actions.clear()

            completed: list[str] = []
            failures: list[tuple[str, BaseException]] = []

            for name, action in actions:
                try:
                    action()
                except Exception as exc:  # every action must run
                    failures.append((name, exc))
                else:
                    completed.append(name)

            self._report = CleanupReport(
                completed=tuple(completed),
                failed=tuple(name for name, _ in failures),
            )

        if failures:
            raise CleanupError(failures)

        return self._report

    def __enter__(self) -> CleanupStack:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            self.run()
        except CleanupError as cleanup_error:
            if exc is None:
                raise

            # Keep the original error as the primary one; record the
            # cleanup failure on it instead of masking it.
            exc.add_note(str(cleanup_error))

        return False
