#!/usr/bin/env bash

set -u
set -o pipefail

ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../.."
    pwd
)"

cd "$ROOT" || exit 1

echo "============================================================"
echo "TASK 13 — EVIDENCE"
echo "============================================================"

python -m py_compile \
    engine/sandbox/evidence/*.py \
    engine/sandbox/lifecycle/timeout.py \
    tests/sandbox/test_evidence_real.py

rc=$?

if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: Task 13 compile rc=$rc"
    exit "$rc"
fi

python -m pytest -q -s \
    tests/sandbox/test_evidence_real.py

rc=$?

if [[ "$rc" -ne 0 ]]; then
    echo "FAIL: Task 13 evidence tests rc=$rc"
    exit "$rc"
fi

echo
echo "TASK13_EVIDENCE_PASS"
