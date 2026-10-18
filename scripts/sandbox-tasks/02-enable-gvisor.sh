#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 02 — ENABLE GVISOR"

require_file engine/sandbox/selector.py
require_file engine/sandbox/manager.py
require_file engine/sandbox/runtime/gvisor.py

compile_sandbox

echo
echo "===== SELECTOR GVISOR ====="

grep -n \
    'RuntimeKind.GVISOR' \
    engine/sandbox/selector.py \
    || fail "GVISOR missing from selector"

echo
echo "===== MANAGER GVISOR ====="

grep -n \
    'GVisorRuntime\|RuntimeKind.GVISOR' \
    engine/sandbox/manager.py \
    || fail "GVISOR missing from manager"

python - <<'PY'
from engine.sandbox.models import (
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.selector import select_runtime

request = SandboxRequest(
    workload_type=WorkloadType.GENERATED_CODE,
    trust_level=TrustLevel.UNTRUSTED,
    command=("true",),
)

selection = select_runtime(request)

print(f"runtime={selection.runtime_kind.value}")
print(f"isolation={selection.isolation_class.value}")
print(f"reason={selection.reason}")

assert selection.runtime_kind == RuntimeKind.GVISOR

print("GVISOR_SELECTOR_OK")
PY

pass "TASK 02"
