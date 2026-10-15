#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

section "TASK 18 — SANDBOX PRODUCTION / ADVERSARIAL MATRIX"

NEW_TESTS=(
    tests/sandbox/test_registry_real.py
    tests/sandbox/test_lifecycle_real.py
    tests/sandbox/test_evidence_real.py
    tests/sandbox/test_network_policy_real.py
    tests/sandbox/test_pro_layer_real.py
    tests/sandbox/test_data_engine_integration_real.py
    tests/sandbox/test_sandbox_adversarial_real.py
)

REAL_RUNTIME_CANDIDATES=(
    tests/sandbox/test_podman_runtime_real.py
    tests/sandbox/test_gvisor_runtime_real.py
    tests/sandbox/test_incus_container_runtime_real.py
    tests/sandbox/test_incus_vm_runtime_real.py
    tests/sandbox/test_qemu_runtime_real.py
    tests/sandbox/test_firecracker_guest_real.py
    tests/sandbox/test_firecracker_runtime_real.py
    tests/sandbox/test_firecracker_matrix_real.py
    tests/sandbox/test_guest_protocol.py
    tests/sandbox/test_manager_real.py
    tests/sandbox/test_selector_real.py
)

REAL_RUNTIME_TESTS=()

for path in "${REAL_RUNTIME_CANDIDATES[@]}"; do
    [[ -f "$path" ]] && REAL_RUNTIME_TESTS+=("$path")
done

echo "New completion tests:"
printf '  %s\n' "${NEW_TESTS[@]}"

echo
echo "Existing real-runtime tests:"
printf '  %s\n' "${REAL_RUNTIME_TESTS[@]}"

echo
echo "===== COMPILE ====="

python -m py_compile \
    engine/sandbox/registry/*.py \
    engine/sandbox/lifecycle/*.py \
    engine/sandbox/evidence/*.py \
    engine/sandbox/policy/network.py \
    engine/sandbox/agentic_harness.py \
    engine/sandbox/pro_layer.py \
    engine/sandbox/data_engine.py \
    "${NEW_TESTS[@]}"

pass "Sandbox completion code compiles"


echo
echo "===== NO MOCKS ====="

if grep -RInE \
    'unittest\.mock|MagicMock|(^|[^A-Za-z])patch\(|monkeypatch' \
    engine/sandbox/registry \
    engine/sandbox/lifecycle \
    engine/sandbox/evidence \
    engine/sandbox/policy/network.py \
    engine/sandbox/agentic_harness.py \
    engine/sandbox/pro_layer.py \
    engine/sandbox/data_engine.py \
    "${NEW_TESTS[@]}"
then
    fail "Mock/fake testing found"
fi

pass "No mocks"


echo
echo "===== COMPLETION TESTS ====="

python -m pytest -q \
    "${NEW_TESTS[@]}"

pass "Tasks 11-17 completion tests"


echo
echo "===== EXISTING REAL RUNTIME MATRIX ====="

if (( ${#REAL_RUNTIME_TESTS[@]} == 0 )); then
    fail "No existing real runtime tests discovered"
fi

python -m pytest -q -s \
    "${REAL_RUNTIME_TESTS[@]}"

pass "Existing real runtime matrix"


echo
echo "===== NETWORK DEFAULT ====="

python - <<'PY'
from engine.sandbox.policy.network import DEFAULT_NETWORK_POLICY

assert not DEFAULT_NETWORK_POLICY.network_enabled
print("PASS: networking disabled by default")
PY


echo
echo "===== DATA ENGINE SCHEMA ====="

python - <<'PY'
from engine.sandbox.data_engine import CANONICAL_FIELDS

assert CANONICAL_FIELDS == (
    "source",
    "category",
    "data_type",
    "value",
    "unit",
)

print("PASS: canonical Data Engine schema")
PY


echo
echo "===== VM IMAGE GIT SAFETY ====="

IMG_RE='\.(qcow2|ext4|img|raw|vmdk|squashfs)$|(^|/)vmlinu[xz]'

TRACKED="$(
    git ls-files |
    grep -Ei "$IMG_RE" ||
    true
)"

if [[ -n "$TRACKED" ]]; then
    echo "$TRACKED"
    fail "VM image/runtime binary tracked by Git"
fi

pass "No VM images tracked"


echo
echo "===== RESIDUAL RUNTIMES ====="

RESIDUE="$(
    {
        pgrep -af 'firecracker --id dataworc-fc-' || true
        pgrep -af 'qemu-system.*dataworc' || true
        podman ps -a \
            --filter name=dataworc- \
            --format '{{.Names}} {{.Status}}' \
            2>/dev/null || true
        incus list \
            --format csv \
            -c n \
            2>/dev/null |
            grep '^dataworc-' || true
    }
)"

if [[ -n "$RESIDUE" ]]; then
    echo "$RESIDUE"
    fail "Sandbox runtime residue detected"
fi

pass "No sandbox runtime residue"


echo
echo "===== DIFF CHECK ====="

git diff --check

pass "git diff --check"


pass "TASK 18"
pass "SANDBOX TASKS 11-18 COMPLETE"
