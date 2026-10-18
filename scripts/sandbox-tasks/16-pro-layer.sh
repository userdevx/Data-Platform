#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

section "TASK 16 — PRO LAYER"

python -m py_compile \
    engine/sandbox/pro_layer.py \
    tests/sandbox/test_pro_layer_real.py

python -m pytest -q \
    tests/sandbox/test_pro_layer_real.py

pass "TASK 16"
