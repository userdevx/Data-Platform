#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

section "TASK 15 — AGENTIC HARNESS SANDBOX BOUNDARY"

python -m py_compile \
    engine/sandbox/agentic_harness.py

grep -q 'class AgenticHarnessSandbox' \
    engine/sandbox/agentic_harness.py \
    || fail "Agentic Harness sandbox adapter missing"

grep -Eq 'podman|firecracker|qemu|incus|gvisor' \
    engine/sandbox/agentic_harness.py \
    && fail "Agentic Harness depends on a concrete runtime" \
    || true

pass "TASK 15"
