#!/usr/bin/env bash
# TASK 09 — Firecracker final gate.
#
# Re-runs the complete Firecracker proof chain:
#   09.2   pinned Firecracker artifacts
#   09.3   shared guest execution protocol
#   09.4   derived guest image
#   09.4.1 systemd-scope guest execution
#   09.5   real KVM/vsock boot proof
#   09.6   FirecrackerRuntime
#   09.7   real production matrix
#   09.7.1 fail-closed run-owner identity
#
# This gate is intentionally scoped to Task 09. Unrelated untracked
# lifecycle/evidence/network-policy work must not affect this milestone.
#
# Read-only for tracked files. Writes only test/run scratch under ~/.cache
# and logs under ~/logs.

set -Eeuo pipefail

source "$(dirname "$0")/common.sh"

BRANCH="sandbox/podman-runtime"

RUN_ROOT="${HOME}/.cache/dataworc/sandbox/firecracker/runs"
TEST_RUN_BASE="${HOME}/.cache/dataworc-run"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PYTEST_BASE="${HOME}/.cache/dataworc-pytest/gate-09-${STAMP}"

export TMPDIR="${TEST_RUN_BASE}"

mkdir -p \
    "$TMPDIR" \
    "$(dirname "$PYTEST_BASE")" \
    "${HOME}/logs"


# ---------------------------------------------------------------------------
# Task 09 scope
# ---------------------------------------------------------------------------

FIRECRACKER_TESTS=(
    tests/sandbox/test_guest_protocol.py
    tests/sandbox/test_firecracker_guest_real.py
    tests/sandbox/test_firecracker_runtime_real.py
    tests/sandbox/test_firecracker_matrix_real.py
    tests/sandbox/test_selector_real.py
)

TASK_09_PYTHON_FILES=(
    engine/sandbox/guest_protocol.py
    engine/sandbox/runtime/firecracker.py
    engine/sandbox/images/guest/dataworc_guest_exec.py
    engine/sandbox/images/firecracker/guest/dataworc_firecracker_agent.py

    scripts/sandbox-tasks/firecracker_pins.py
    scripts/sandbox-tasks/firecracker_guest_image.py
    scripts/sandbox-tasks/verify-firecracker-pins.py
    scripts/sandbox-tasks/build-firecracker-guest.py
    scripts/sandbox-tasks/prove-firecracker-boot.py

    "${FIRECRACKER_TESTS[@]}"
)

REQUIRED_FILES=(
    engine/sandbox/guest_protocol.py
    engine/sandbox/runtime/firecracker.py

    engine/sandbox/images/firecracker/pinned.json

    engine/sandbox/images/guest/dataworc_guest_exec.py
    engine/sandbox/images/firecracker/guest/dataworc_firecracker_agent.py
    engine/sandbox/images/firecracker/guest/dataworc-firecracker-agent.service

    scripts/sandbox-tasks/firecracker_pins.py
    scripts/sandbox-tasks/firecracker_guest_image.py
    scripts/sandbox-tasks/verify-firecracker-pins.py
    scripts/sandbox-tasks/build-firecracker-guest.py
    scripts/sandbox-tasks/prove-firecracker-boot.py

    "${FIRECRACKER_TESTS[@]}"
)


# ---------------------------------------------------------------------------
# Residue
# ---------------------------------------------------------------------------

vm_residue() {
    pgrep -af 'firecracker --id dataworc-fc-' || true
}


dir_residue() {
    {
        if [[ -d "$RUN_ROOT" ]]; then
            find \
                "$RUN_ROOT" \
                -mindepth 1 \
                -maxdepth 1 \
                -name 'dataworc-fc-*'
        fi

        if [[ -d "$TEST_RUN_BASE" ]]; then
            find \
                "$TEST_RUN_BASE" \
                -mindepth 1 \
                -maxdepth 1 \
                \( \
                    -name 'fct-*' \
                    -o -name 'fcm-*' \
                    -o -name 'dataworc-fc-*' \
                \)
        fi
    } 2>/dev/null || true
}


check_residue() {
    local when="$1"
    local vms
    local dirs

    vms="$(vm_residue)"

    if [[ -n "$vms" ]]; then
        echo "$vms"
        fail "Residual Firecracker VM process ($when)"
    fi

    dirs="$(dir_residue)"

    if [[ -n "$dirs" ]]; then
        echo "$dirs"
        fail "Stale Firecracker run directory ($when)"
    fi

    pass "No Firecracker VMs or stale run directories ($when)"
}


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

tracked_clean() {
    git diff --quiet &&
        git diff --cached --quiet
}


# ---------------------------------------------------------------------------
# Command result helpers
# ---------------------------------------------------------------------------

expect_last_line() {
    local expected="$1"

    shift

    local output

    if ! output="$("$@" 2>&1)"; then
        echo "$output"
        fail "$* exited non-zero"
    fi

    echo "$output" | tail -n 5

    if [[ "$(echo "$output" | tail -n 1)" != "$expected" ]]; then
        fail "$* did not end with '$expected'"
    fi
}


# ---------------------------------------------------------------------------
# Scoped Task 09 checks
# ---------------------------------------------------------------------------

check_task_09_no_mocks() {
    local result

    result="$(
        grep -nHE \
            'unittest\.mock|MagicMock|(^|[^A-Za-z])patch\(|monkeypatch' \
            "${TASK_09_PYTHON_FILES[@]}" \
            2>/dev/null \
            || true
    )"

    if [[ -n "$result" ]]; then
        echo "$result"
        fail "Mock/fake testing found in Task 09 files"
    fi

    pass "No mocks in Task 09 files"
}


compile_task_09() {
    python -m py_compile \
        "${TASK_09_PYTHON_FILES[@]}"

    pass "Task 09 Python files compile"
}


# ---------------------------------------------------------------------------
# Image integrity
# ---------------------------------------------------------------------------

image_digests() {
    python - <<'PY'
import json
from pathlib import Path

from engine.sandbox.runtime.firecracker import (
    DEFAULT_PIN_FILE,
    FirecrackerRuntime,
    sha256_file,
)

pin = json.loads(
    DEFAULT_PIN_FILE.read_text(
        encoding="utf-8",
    )
)

store = Path(
    pin["artifacts"]["store"]
).expanduser()

base = (
    store
    / pin["artifacts"]["rootfs"]["file"]
)

derived = FirecrackerRuntime().resolve_artifacts()

print(
    "base="
    f"{sha256_file(base)} "
    "pinned="
    f"{pin['artifacts']['rootfs']['sha256']}"
)

print(
    "derived="
    f"{sha256_file(derived.rootfs)} "
    "dir="
    f"{derived.guest_image_dir.name}"
)
PY
}


# ---------------------------------------------------------------------------
# Real test chain
# ---------------------------------------------------------------------------

run_pytest() {
    local log="${PYTEST_BASE}.log"
    local summary

    rm -rf "$PYTEST_BASE"

    python -m pytest \
        -q \
        -s \
        -p no:cacheprovider \
        -rs \
        "${FIRECRACKER_TESTS[@]}" \
        --basetemp "$PYTEST_BASE" \
        2>&1 |
        tee "$log"

    local pytest_rc="${PIPESTATUS[0]}"

    if [[ "$pytest_rc" -ne 0 ]]; then
        fail "Firecracker test chain failed (log: $log)"
    fi

    summary="$(tail -n 1 "$log")"

    # Accept only a clean:
    #
    #     N passed in Ts
    #
    # Reject skipped, failed, xfailed, xpassed, errors, warnings,
    # "no tests ran", or combined summaries containing commas.

    if [[ ! "$summary" =~ ^[0-9]+[[:space:]]+passed[[:space:]]+in[[:space:]]+[0-9.]+s([[:space:]]+\([0-9:]+\))?$ ]]; then
        fail \
            "Firecracker test chain summary not clean: '$summary' " \
            "(log: $log)"
    fi

    pass "Firecracker test chain: $summary"
}


# ===========================================================================
# Start
# ===========================================================================

section "TASK 09 — FIRECRACKER (final gate)"


# ---------------------------------------------------------------------------
# Repository state
# ---------------------------------------------------------------------------

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
    fail "Not on $BRANCH (current: $CURRENT_BRANCH)"
fi

if ! tracked_clean; then
    git status --short --untracked-files=no
    fail "Tracked tree not clean"
fi

HEAD_SHA="$(git rev-parse HEAD)"

pass \
    "Gate subject: $BRANCH @ $HEAD_SHA " \
    "(tracked tree clean)"


git fetch --quiet origin "$BRANCH" \
    || fail "Unable to fetch origin/$BRANCH"

REMOTE_SHA="$(git rev-parse "origin/$BRANCH")"

if [[ "$REMOTE_SHA" != "$HEAD_SHA" ]]; then
    echo "local=$HEAD_SHA"
    echo "remote=$REMOTE_SHA"
    fail "origin/$BRANCH != HEAD; push or pull before gating"
fi

pass "origin/$BRANCH == HEAD"


# ---------------------------------------------------------------------------
# Host preconditions
# ---------------------------------------------------------------------------

check_kvm
require_command pgrep

if [[ ! -x /usr/bin/setpriv ]]; then
    fail "Missing /usr/bin/setpriv"
fi

if [[ "$(stat -c %u /usr/bin/setpriv)" != 0 ]]; then
    fail "/usr/bin/setpriv is not root-owned"
fi

pass "setpriv present and root-owned"


# ---------------------------------------------------------------------------
# Required source
# ---------------------------------------------------------------------------

for file in "${REQUIRED_FILES[@]}"; do
    require_file "$file"
done

pass "Required Firecracker files present"


# ---------------------------------------------------------------------------
# Task 09 scoped static validation
# ---------------------------------------------------------------------------

check_task_09_no_mocks
compile_task_09


# ---------------------------------------------------------------------------
# Production wiring boundary
# ---------------------------------------------------------------------------

python - <<'PY' \
    || fail "Firecracker must not be wired into selector/manager yet"

from pathlib import Path

from engine.sandbox.models import RuntimeKind
from engine.sandbox.selector import _IMPLEMENTED_RUNTIMES

assert RuntimeKind.FIRECRACKER not in _IMPLEMENTED_RUNTIMES

manager_text = Path(
    "engine/sandbox/manager.py"
).read_text(
    encoding="utf-8",
)

assert "firecracker" not in manager_text.lower()
PY

pass \
    "Firecracker not wired into selector/manager " \
    "(by design until 12W)"


# ---------------------------------------------------------------------------
# Initial residue
# ---------------------------------------------------------------------------

check_residue "before"


# ===========================================================================
# 09.2 / 09.4
# ===========================================================================

section "09.2 pins / 09.4 derived guest image"

expect_last_line \
    "PASS: TASK 09.2" \
    python \
    scripts/sandbox-tasks/verify-firecracker-pins.py

expect_last_line \
    "PASS: TASK 09.4" \
    python \
    scripts/sandbox-tasks/build-firecracker-guest.py \
    --verify


DIGESTS_BEFORE="$(
    image_digests
)" || fail "Unable to resolve Firecracker artifacts"

echo "$DIGESTS_BEFORE"

BASE_SHA=""
PINNED_SHA=""

read -r BASE_SHA PINNED_SHA < <(
    echo "$DIGESTS_BEFORE" |
        sed -n \
            '1s/base=\(\S*\) pinned=\(\S*\)/\1 \2/p'
) || true

if [[ -z "$BASE_SHA" ]]; then
    fail "Unable to read base rootfs digest"
fi

if [[ -z "$PINNED_SHA" ]]; then
    fail "Unable to read pinned rootfs digest"
fi

if [[ "$BASE_SHA" != "$PINNED_SHA" ]]; then
    echo "base=$BASE_SHA"
    echo "pin =$PINNED_SHA"
    fail "Base rootfs differs from pin"
fi

pass "Base rootfs matches pin; derived image resolved"


# ===========================================================================
# 09.3 / 09.4 / 09.6 / 09.7
# ===========================================================================

section \
    "09.3 / 09.4 / 09.6 / 09.7 tests " \
    "(real KVM, no mocks)"

run_pytest

check_residue "after tests"


# ===========================================================================
# 09.5
# ===========================================================================

section "09.5 boot proof"

expect_last_line \
    "PASS: TASK 09.5" \
    python \
    scripts/sandbox-tasks/prove-firecracker-boot.py

check_residue "after boot proof"


# ===========================================================================
# Integrity
# ===========================================================================

section "Integrity after the full chain"

DIGESTS_AFTER="$(
    image_digests
)" || fail "Unable to resolve Firecracker artifacts"

if [[ "$DIGESTS_AFTER" != "$DIGESTS_BEFORE" ]]; then
    echo
    echo "before:"
    echo "$DIGESTS_BEFORE"

    echo
    echo "after:"
    echo "$DIGESTS_AFTER"

    fail "Firecracker images changed during the gate"
fi

pass "Base and derived images unchanged"


expect_last_line \
    "PASS: TASK 09.2" \
    python \
    scripts/sandbox-tasks/verify-firecracker-pins.py


check_residue "final"


if ! tracked_clean; then
    git status --short --untracked-files=no
    fail "Gate modified tracked files"
fi

CURRENT_HEAD="$(git rev-parse HEAD)"

if [[ "$CURRENT_HEAD" != "$HEAD_SHA" ]]; then
    echo "before=$HEAD_SHA"
    echo "after =$CURRENT_HEAD"
    fail "HEAD moved during the gate"
fi

pass "Tracked tree unchanged; HEAD still $HEAD_SHA"


# ===========================================================================
# Final
# ===========================================================================

pass "TASK 09 @ $HEAD_SHA"
