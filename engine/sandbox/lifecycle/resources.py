from __future__ import annotations

import math

from engine.sandbox.models import SandboxRequest


class ResourcePolicyError(ValueError):
    pass


class ResourcePolicy:
    MIN_CPU_COUNT = 0.01
    MAX_CPU_COUNT = 32.0

    MIN_MEMORY_MB = 1
    MAX_MEMORY_MB = 32768

    MIN_TIMEOUT_SECONDS = 0.01
    MAX_TIMEOUT_SECONDS = 86400.0

    MIN_PIDS = 1
    MAX_PIDS = 4096

    def validate(
        self,
        request: SandboxRequest,
    ) -> None:
        if not isinstance(request, SandboxRequest):
            raise ResourcePolicyError(
                "request must be a SandboxRequest"
            )

        limits = request.limits

        cpu_count = limits.cpu_count
        memory_mb = limits.memory_mb
        timeout = limits.timeout_seconds
        pids = limits.pids

        if (
            isinstance(cpu_count, bool)
            or not isinstance(
                cpu_count,
                (int, float),
            )
        ):
            raise ResourcePolicyError(
                "cpu_count must be numeric"
            )

        cpu_value = float(cpu_count)

        if not math.isfinite(cpu_value):
            raise ResourcePolicyError(
                "cpu_count must be finite"
            )

        if not (
            self.MIN_CPU_COUNT
            <= cpu_value
            <= self.MAX_CPU_COUNT
        ):
            raise ResourcePolicyError(
                "cpu_count outside sandbox policy"
            )

        if (
            isinstance(memory_mb, bool)
            or not isinstance(memory_mb, int)
        ):
            raise ResourcePolicyError(
                "memory_mb must be an integer"
            )

        if not (
            self.MIN_MEMORY_MB
            <= memory_mb
            <= self.MAX_MEMORY_MB
        ):
            raise ResourcePolicyError(
                "memory_mb outside sandbox policy"
            )

        if (
            isinstance(timeout, bool)
            or not isinstance(
                timeout,
                (int, float),
            )
        ):
            raise ResourcePolicyError(
                "timeout_seconds must be numeric"
            )

        timeout_value = float(timeout)

        if not math.isfinite(timeout_value):
            raise ResourcePolicyError(
                "timeout_seconds must be finite"
            )

        if not (
            self.MIN_TIMEOUT_SECONDS
            <= timeout_value
            <= self.MAX_TIMEOUT_SECONDS
        ):
            raise ResourcePolicyError(
                "timeout_seconds outside sandbox policy"
            )

        if (
            isinstance(pids, bool)
            or not isinstance(pids, int)
        ):
            raise ResourcePolicyError(
                "pids must be an integer"
            )

        if not (
            self.MIN_PIDS
            <= pids
            <= self.MAX_PIDS
        ):
            raise ResourcePolicyError(
                "pids outside sandbox policy"
            )
