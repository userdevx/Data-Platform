#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

section "TASK 14 — NETWORK POLICY"

python -m py_compile \
    engine/sandbox/policy/network.py \
    tests/sandbox/test_network_policy_real.py

python -m pytest -q \
    tests/sandbox/test_network_policy_real.py

pass "TASK 14"
