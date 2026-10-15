#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../.."
  pwd
)"

cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python}"

echo "===== TASK 12: SANDBOX LIFECYCLE ====="
echo "repo=$ROOT"
echo

echo "===== 1. COMPILE ====="

"$PYTHON_BIN" -m py_compile \
  engine/sandbox/process_identity.py \
  engine/sandbox/lifecycle/__init__.py \
  engine/sandbox/lifecycle/cancellation.py \
  engine/sandbox/lifecycle/cleanup.py \
  engine/sandbox/lifecycle/containment.py \
  engine/sandbox/lifecycle/controller.py \
  engine/sandbox/lifecycle/provisioning.py \
  engine/sandbox/lifecycle/resources.py \
  engine/sandbox/lifecycle/timeout.py \
  engine/sandbox/lifecycle/workspace.py \
  engine/sandbox/runtime/podman.py \
  engine/sandbox/runtime/gvisor.py \
  engine/sandbox/runtime/incus_container.py \
  engine/sandbox/runtime/incus_vm.py \
  engine/sandbox/runtime/qemu.py \
  engine/sandbox/runtime/firecracker.py

echo "TASK12_COMPILE_OK"
echo

echo "===== 2. NO TASK 13 DEPENDENCY ====="

if grep -RIn \
  'engine\.sandbox\.evidence' \
  engine/sandbox/lifecycle
then
  echo "FAIL: Task 12 lifecycle depends on Task 13 evidence"
  exit 1
fi

echo "TASK12_NO_TASK13_DEPENDENCY_OK"
echo

echo "===== 3. NO MOCK-BASED TESTING ====="

if grep -En \
  'unittest\.mock|MagicMock|monkeypatch|Mock\(' \
  tests/sandbox/test_lifecycle_real.py \
  tests/sandbox/test_lifecycle_workspace_adversarial_real.py \
  tests/sandbox/test_lifecycle_recovery_real.py \
  tests/sandbox/test_lifecycle_containment_real.py \
  tests/sandbox/test_lifecycle_incus_cleanup_real.py
then
  echo "FAIL: mock-based Task 12 test detected"
  exit 1
fi

echo "TASK12_REAL_TESTS_ONLY_OK"
echo

echo "===== 4. CORE LIFECYCLE TESTS ====="

"$PYTHON_BIN" -m pytest -q -s \
  tests/sandbox/test_lifecycle_real.py \
  tests/sandbox/test_lifecycle_workspace_adversarial_real.py \
  tests/sandbox/test_lifecycle_recovery_real.py \
  tests/sandbox/test_lifecycle_containment_real.py

echo "TASK12_CORE_LIFECYCLE_OK"
echo

echo "===== 5. REAL INCUS CLEANUP ====="

"$PYTHON_BIN" -m pytest -q -s \
  tests/sandbox/test_lifecycle_incus_cleanup_real.py

echo "TASK12_INCUS_CLEANUP_OK"
echo

echo "===== 6. REAL RUNTIME REGRESSION ====="

"$PYTHON_BIN" -m pytest -q -s \
  tests/sandbox/test_podman_runtime.py \
  tests/sandbox/test_gvisor_runtime_real.py \
  tests/sandbox/test_qemu_runtime_real.py \
  tests/sandbox/test_firecracker_runtime_real.py \
  tests/sandbox/test_firecracker_guest_real.py \
  tests/sandbox/test_firecracker_matrix_real.py

echo "TASK12_RUNTIME_REGRESSION_OK"
echo

echo "===== 7. HARDWARE MANAGER REGRESSION ====="

"$PYTHON_BIN" -m pytest -q -s \
  tests/sandbox/test_manager_real.py::test_manager_real_hardware_execution

echo "TASK12_MANAGER_HARDWARE_OK"
echo

echo "===== 8. IMAGE REGISTRY REGRESSION ====="

"$PYTHON_BIN" -m pytest -q -s \
  tests/sandbox/test_registry_real.py

echo "TASK12_REGISTRY_REGRESSION_OK"
echo

echo "===== 9. POST-TEST RESOURCE RESIDUE ====="

residue=0

PODMAN_RESIDUE="$(
  podman ps -a \
    --format '{{.Names}}' \
    2>/dev/null \
    | grep '^dataworc-podman-' \
    || true
)"

if [[ -n "$PODMAN_RESIDUE" ]]; then
  echo "FAIL: Podman sandbox residue"
  printf '%s\n' "$PODMAN_RESIDUE"
  residue=1
fi

DOCKER_RESIDUE="$(
  docker ps -a \
    --format '{{.Names}}' \
    2>/dev/null \
    | grep '^dataworc-gvisor-' \
    || true
)"

if [[ -n "$DOCKER_RESIDUE" ]]; then
  echo "FAIL: gVisor/Docker sandbox residue"
  printf '%s\n' "$DOCKER_RESIDUE"
  residue=1
fi

INCUS_RESIDUE="$(
  incus list \
    --format=csv \
    -c n \
    2>/dev/null \
    | grep -E '^dataworc-(sandbox|vm)-' \
    || true
)"

if [[ -n "$INCUS_RESIDUE" ]]; then
  echo "FAIL: Incus sandbox residue"
  printf '%s\n' "$INCUS_RESIDUE"
  residue=1
fi

QEMU_RESIDUE="$(
  pgrep -af 'qemu-system.*dataworc-qemu-' \
    || true
)"

if [[ -n "$QEMU_RESIDUE" ]]; then
  echo "FAIL: QEMU sandbox process residue"
  printf '%s\n' "$QEMU_RESIDUE"
  residue=1
fi

FIRECRACKER_RESIDUE="$(
  pgrep -af 'firecracker.*dataworc-' \
    || true
)"

if [[ -n "$FIRECRACKER_RESIDUE" ]]; then
  echo "FAIL: Firecracker sandbox process residue"
  printf '%s\n' "$FIRECRACKER_RESIDUE"
  residue=1
fi

SYSTEMD_SCOPE_RESIDUE="$(
  systemctl --user \
    list-units \
    --type=scope \
    --all \
    --no-legend \
    'dataworc-sandbox-*.scope' \
    2>/dev/null \
    | grep 'dataworc-sandbox-' \
    || true
)"

if [[ -n "$SYSTEMD_SCOPE_RESIDUE" ]]; then
  echo "FAIL: systemd sandbox scope residue"
  printf '%s\n' "$SYSTEMD_SCOPE_RESIDUE"
  residue=1
fi

if [[ "$residue" -ne 0 ]]; then
  exit 1
fi

echo "TASK12_RUNTIME_RESIDUE_CLEAN"
echo

echo "======================================"
echo "TASK12_LIFECYCLE_PASS"
echo "======================================"
