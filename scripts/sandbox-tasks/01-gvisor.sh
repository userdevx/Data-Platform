#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 01 — REAL GVISOR"

require_command docker
require_command runsc
require_file engine/sandbox/runtime/gvisor.py

docker info >/dev/null

docker info --format '{{json .Runtimes}}' \
    | grep -q runsc \
    || fail "runsc is not registered with Docker"

docker image inspect alpine:latest >/dev/null \
    || fail "alpine:latest is not provisioned locally"

python - <<'PY'
from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.gvisor import GVisorRuntime

request = SandboxRequest(
    workload_type=WorkloadType.GENERATED_CODE,
    trust_level=TrustLevel.UNTRUSTED,
    command=(
        "sh",
        "-c",
        """
echo GVISOR_RUNTIME_OK
uname -r
ip addr show
grep '^CapEff:' /proc/self/status
""",
    ),
    limits=ResourceLimits(
        cpu_count=0.5,
        memory_mb=256,
        timeout_seconds=10,
        pids=64,
    ),
)

result = GVisorRuntime().execute(request)

print(result.stdout)

assert result.exit_code == 0
assert result.timed_out is False
assert "GVISOR_RUNTIME_OK" in result.stdout
assert "-gvisor" in result.stdout
assert "127.0.0.1" in result.stdout
assert "eth0" not in result.stdout
assert "CapEff:\t0000000000000000" in result.stdout

print("REAL_GVISOR_EXECUTION_OK")
PY

python - <<'PY'
from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.gvisor import GVisorRuntime

request = SandboxRequest(
    workload_type=WorkloadType.GENERATED_CODE,
    trust_level=TrustLevel.UNTRUSTED,
    command=("sh", "-c", "echo TIMEOUT_STARTED; sleep 30"),
    limits=ResourceLimits(
        cpu_count=0.25,
        memory_mb=128,
        timeout_seconds=3,
        pids=32,
    ),
)

result = GVisorRuntime().execute(request)

print(
    f"exit_code={result.exit_code}\n"
    f"timed_out={result.timed_out}\n"
    f"duration={result.duration_seconds}"
)

assert result.exit_code == 124
assert result.timed_out is True

print("REAL_GVISOR_TIMEOUT_OK")
PY

check_cleanup
pass "TASK 01"
