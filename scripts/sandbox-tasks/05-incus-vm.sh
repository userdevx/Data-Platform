#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 05 — INCUS VM"

check_kvm
require_command incus
require_file engine/sandbox/runtime/incus_vm.py

incus image info dataworc-sandbox-ubuntu-24.04-vm >/dev/null \
    || fail "Incus VM image missing"

python - <<'PY'
from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.incus_vm import IncusVmRuntime

request = SandboxRequest(
    workload_type=WorkloadType.SYSTEM,
    trust_level=TrustLevel.LIMITED,
    command=(
        "sh",
        "-c",
        """
echo INCUS_VM_OK
systemd-detect-virt
nproc
uname -r
ip addr show
""",
    ),
    requires_vm_boundary=True,
    limits=ResourceLimits(
        cpu_count=2,
        memory_mb=512,
        timeout_seconds=60,
        pids=64,
    ),
)

result = IncusVmRuntime().execute(request)

print(result.stdout)

assert result.exit_code == 0
assert result.timed_out is False
assert "INCUS_VM_OK" in result.stdout
assert "kvm" in result.stdout

print("REAL_INCUS_VM_OK")
PY

check_cleanup
pass "TASK 05"
