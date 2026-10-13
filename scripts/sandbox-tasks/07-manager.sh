#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 07 — REAL SANDBOX MANAGER"

require_file tests/sandbox/test_manager_real.py

no_mocks

python -m pytest \
    tests/sandbox/test_manager_real.py \
    -q -s

check_cleanup

pass "TASK 07"
