#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 08 — QEMU/KVM"

check_kvm
require_command qemu-system-x86_64

require_file engine/sandbox/runtime/qemu.py
require_file tests/sandbox/test_qemu_runtime_real.py

no_mocks

python -m pytest \
    tests/sandbox/test_qemu_runtime_real.py \
    -q -s

if pgrep -af 'qemu-system.*dataworc' >/dev/null; then
    pgrep -af 'qemu-system.*dataworc'
    fail "Residual DataWorc QEMU process"
fi

pass "TASK 08"
