#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 03 — REAL DISCOVERY"

python - <<'PY'
from engine.sandbox.discovery import discover_runtimes

results = {
    item.runtime_kind.value: item
    for item in discover_runtimes()
}

required = {
    "podman",
    "incus_container",
    "gvisor",
    "qemu_kvm",
    "incus_vm",
}

for name, item in results.items():
    print(
        f"{name:18} "
        f"available={item.available!s:5} "
        f"isolation={item.isolation_class.value:18} "
        f"executable={item.executable} "
        f"reason={item.reason}"
    )

for name in required:
    assert name in results, name
    assert results[name].available is True, (
        name,
        results[name].reason,
    )

print("REAL_DISCOVERY_OK")
PY

pass "TASK 03"
