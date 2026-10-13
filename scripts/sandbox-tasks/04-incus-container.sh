#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 04 — INCUS CONTAINER"

require_command incus
require_file engine/sandbox/runtime/incus_container.py

incus image info dataworc-sandbox-ubuntu-24.04 >/dev/null \
    || fail "Incus container image missing"

python - <<'PY'
from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.incus_container import IncusContainerRuntime

request = SandboxRequest(
    workload_type=WorkloadType.TEST,
    trust_level=TrustLevel.TRUSTED,
    command=(
        "sh",
        "-c",
        """
echo INCUS_CONTAINER_OK
hostname
cat /sys/fs/cgroup/memory.max
ip addr show
""",
    ),
    limits=ResourceLimits(
        cpu_count=0.5,
        memory_mb=256,
        timeout_seconds=15,
        pids=64,
    ),
)

result = IncusContainerRuntime().execute(request)

print(result.stdout)

assert result.exit_code == 0
assert result.timed_out is False
assert "INCUS_CONTAINER_OK" in result.stdout
assert "268435456" in result.stdout

print("REAL_INCUS_CONTAINER_OK")
PY

check_cleanup
pass "TASK 04"
