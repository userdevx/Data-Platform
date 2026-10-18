#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "$0")/common.sh"

section "TASK 11 — RUNTIME / IMAGE REGISTRY + DURABLE TRUST"

require_file engine/sandbox/images/firecracker/pinned.json
require_file engine/sandbox/registry/__init__.py
require_file engine/sandbox/registry/models.py
require_file engine/sandbox/registry/trust.py
require_file engine/sandbox/registry/registry.py
require_file engine/sandbox/registry/firecracker.py
require_file tests/sandbox/test_registry_real.py

echo
echo "===== COMPILE ====="

python -m py_compile \
    engine/sandbox/registry/*.py \
    tests/sandbox/test_registry_real.py

pass "Task 11 Python files compile"

echo
echo "===== NO MOCKS ====="

if grep -RniE \
    'unittest\.mock|MagicMock|monkeypatch|(^|[^[:alnum:]_])patch\(' \
    engine/sandbox/registry \
    tests/sandbox/test_registry_real.py
then
    fail "Mocks/fakes found in Task 11"
fi

pass "No mocks in Task 11"

echo
echo "===== REGISTRY TESTS ====="

python -m pytest -q -s \
    tests/sandbox/test_registry_real.py

pass "Task 11 registry tests"

echo
echo "===== REAL FIRECRACKER TRUST ====="

python - <<'PY'
from engine.sandbox.models import RuntimeKind
from engine.sandbox.registry import load_firecracker_registry
from engine.sandbox.runtime.firecracker import DEFAULT_PIN_FILE

registry = load_firecracker_registry(
    pin_file=DEFAULT_PIN_FILE,
)

reports = registry.verify_runtime(
    RuntimeKind.FIRECRACKER.value,
)

for report in reports:
    print(
        f"{report.artifact}: "
        f"{report.status.value} "
        f"{report.path}"
    )

if not reports:
    raise SystemExit("FAIL: Firecracker registry is empty")

if not all(report.trusted for report in reports):
    raise SystemExit(
        "FAIL: Firecracker registry contains untrusted artifacts"
    )

registry.assert_trusted(
    RuntimeKind.FIRECRACKER.value,
)

print("REAL_FIRECRACKER_REGISTRY_TRUST_OK")
PY

pass "Real Firecracker artifacts trusted"

echo
echo "===== QEMU TRUST BOUNDARY ====="

python - <<'PY'
from engine.sandbox.models import RuntimeKind
from engine.sandbox.registry import (
    RegistryError,
    load_firecracker_registry,
)
from engine.sandbox.runtime.firecracker import DEFAULT_PIN_FILE

registry = load_firecracker_registry(
    pin_file=DEFAULT_PIN_FILE,
)

try:
    registry.runtime(RuntimeKind.QEMU_KVM.value)
except RegistryError:
    print("QEMU_LEGACY_ARTIFACTS_NOT_BLESSED_OK")
else:
    raise SystemExit(
        "FAIL: QEMU was marked trusted without durable provenance"
    )
PY

pass "Legacy QEMU images are not promoted to Task 11 trust"

echo
echo "===== VM IMAGE GIT SAFETY ====="

if git ls-files | grep -Eq \
    '\.(qcow2|ext4|img|squashfs)$|(^|/)vmlinux[^/]*$'
then
    git ls-files | grep -E \
        '\.(qcow2|ext4|img|squashfs)$|(^|/)vmlinux[^/]*$'
    fail "VM image bytes are tracked by Git"
fi

pass "No VM image bytes tracked"

git diff --check

pass "git diff --check"
pass "TASK 11"
