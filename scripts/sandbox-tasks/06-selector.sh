#!/usr/bin/env bash
source "$(dirname "$0")/common.sh"

section "TASK 06 — REAL SELECTOR"

require_file tests/sandbox/test_selector_real.py

no_mocks

python -m pytest \
    tests/sandbox/test_selector_real.py \
    -q -s

pass "TASK 06"
