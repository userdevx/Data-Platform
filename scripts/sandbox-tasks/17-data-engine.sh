#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

section "TASK 17 — DATA ENGINE INTEGRATION"

python -m py_compile \
    engine/sandbox/data_engine.py \
    tests/sandbox/test_data_engine_integration_real.py

python -m pytest -q \
    tests/sandbox/test_data_engine_integration_real.py

grep -RIn 'sensor_type' \
    engine/sandbox/data_engine.py \
    tests/sandbox/test_data_engine_integration_real.py \
    | grep -v '"sensor_type" not in record' \
    && fail "non-canonical sensor_type found" \
    || true

pass "TASK 17"
