#!/usr/bin/env bash

set -u
set -o pipefail

ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../.."
    pwd
)"

cd "$ROOT" || exit 1


COMPLETION_TESTS=(
    tests/sandbox/test_registry_real.py
    tests/sandbox/test_lifecycle_real.py
    tests/sandbox/test_evidence_real.py
    tests/sandbox/test_network_policy_real.py
    tests/sandbox/test_pro_layer_real.py
    tests/sandbox/test_data_engine_integration_real.py
    tests/sandbox/test_sandbox_adversarial_real.py
)

REAL_RUNTIME_TESTS=(
    tests/sandbox/test_gvisor_runtime_real.py
    tests/sandbox/test_qemu_runtime_real.py
    tests/sandbox/test_firecracker_guest_real.py
    tests/sandbox/test_firecracker_runtime_real.py
    tests/sandbox/test_firecracker_matrix_real.py
    tests/sandbox/test_guest_protocol.py
    tests/sandbox/test_manager_real.py
    tests/sandbox/test_selector_real.py
)


echo "============================================================"
echo "TASK 18 — PRODUCTION / ADVERSARIAL MATRIX"
echo "============================================================"


echo
echo "===== COMPILE ====="

python -m compileall -q \
    engine/sandbox \
    tests/sandbox

rc=$?

if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: Task 18 compile rc=$rc"
    exit "$rc"
fi

echo "TASK18_COMPILE_OK"


echo
echo "===== NO MOCKS ====="

forbidden="$(
    grep -RInE \
        'unittest\.mock|MagicMock|Mock\(|monkeypatch' \
        tests/sandbox \
        --include='test_*.py' \
        || true
)"

if [[ -n "$forbidden" ]]; then
    echo "FAIL: mock/fake tests detected"
    printf '%s\n' "$forbidden"
    exit 1
fi

echo "TASK18_REAL_TESTS_ONLY_OK"


echo
echo "===== COMPLETION TESTS ====="

python -m pytest -q -s \
    "${COMPLETION_TESTS[@]}"

rc=$?

if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: Task 18 completion matrix rc=$rc"
    exit "$rc"
fi

echo "TASK18_COMPLETION_MATRIX_OK"


echo
echo "===== REAL RUNTIME MATRIX ====="

python -m pytest -q -s \
    "${REAL_RUNTIME_TESTS[@]}"

rc=$?

if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: Task 18 runtime matrix rc=$rc"
    exit "$rc"
fi

echo "TASK18_RUNTIME_MATRIX_OK"


echo
echo "======================================"
echo "TASK18_PRODUCTION_MATRIX_PASS"
echo "======================================"
