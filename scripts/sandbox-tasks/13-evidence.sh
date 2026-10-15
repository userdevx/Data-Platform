#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

section "TASK 13 — EVIDENCE"

python -m py_compile \
    engine/sandbox/evidence/*.py \
    tests/sandbox/test_evidence_real.py

python -m pytest -q \
    tests/sandbox/test_evidence_real.py

pass "TASK 13"
