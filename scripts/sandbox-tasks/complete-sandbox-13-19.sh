#!/usr/bin/env bash
set -Eeuo pipefail


# ============================================================
# DataWorc Sandbox Completion Controller
#
# Completes Tasks:
#   13 - Evidence
#   14 - Network Policy
#   15 - Agentic Harness
#   16 - Pro Layer
#   17 - Data Engine Integration
#   18 - Production / Adversarial Matrix
#   19 - Final Sandbox Verification
#
# Every task receives:
#   - dedicated log
#   - syntax / compile validation
#   - real gate execution
#   - selective Git staging
#   - staged diff validation
#   - commit
#   - push
#   - exact remote HEAD verification
#
# Fail closed:
#   Any failed task stops the controller.
# ============================================================


ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../.."
    pwd
)"

cd "$ROOT"


EXPECTED_BRANCH="sandbox/podman-runtime"
REMOTE="${SANDBOX_REMOTE:-origin}"

SESSION_STAMP="$(
    date -u +%Y%m%dT%H%M%SZ
)"

LOG_ROOT="${SANDBOX_LOG_ROOT:-$HOME/logs/sandbox-13-19/$SESSION_STAMP}"

SUMMARY_LOG="$LOG_ROOT/summary.log"

mkdir -p "$LOG_ROOT"


# ------------------------------------------------------------
# Common helpers
# ------------------------------------------------------------

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}


summary() {
    printf '%s | %s\n' \
        "$(timestamp)" \
        "$*" \
        | tee -a "$SUMMARY_LOG"
}


fail() {
    summary "FAIL | $*"

    echo
    echo "======================================"
    echo "SANDBOX COMPLETION STOPPED"
    echo "======================================"
    echo "reason=$*"
    echo "summary_log=$SUMMARY_LOG"
    echo

    exit 1
}


require_branch() {
    local branch

    branch="$(
        git branch --show-current
    )"

    if [[ "$branch" != "$EXPECTED_BRANCH" ]]; then
        fail \
            "expected branch $EXPECTED_BRANCH; actual branch=$branch"
    fi

    summary \
        "BRANCH_OK | $branch"
}


require_no_preexisting_stage() {
    if ! git diff --cached --quiet; then
        echo
        echo "===== PRE-EXISTING STAGED FILES ====="
        git diff --cached --name-status

        fail \
            "staged changes already exist before task execution"
    fi
}


remote_head() {
    git ls-remote \
        "$REMOTE" \
        "refs/heads/$EXPECTED_BRANCH" \
        | awk '{print $1}'
}


verify_remote_head() {
    local task="$1"
    local local_head
    local remote

    local_head="$(
        git rev-parse HEAD
    )"

    remote="$(
        remote_head
    )"

    echo
    echo "local_head=$local_head"
    echo "remote_head=$remote"

    if [[ -z "$remote" ]]; then
        fail \
            "Task $task remote branch HEAD was not returned"
    fi

    if [[ "$local_head" != "$remote" ]]; then
        fail \
            "Task $task local HEAD does not match remote HEAD"
    fi

    summary \
        "TASK_${task}_REMOTE_HEAD_VERIFIED | $local_head"
}


run_logged_task() {
    local task="$1"
    local label="$2"
    local log="$LOG_ROOT/task-${task}.log"
    local rc

    echo
    echo "======================================"
    echo "TASK $task — $label"
    echo "======================================"
    echo "log=$log"
    echo

    summary \
        "TASK_${task}_START | $label | log=$log"

    set +e

    (
        set -Eeuo pipefail

        task_body "$task"
    ) 2>&1 | tee "$log"

    rc=${PIPESTATUS[0]}

    set -e

    echo
    echo "task_${task}_rc=$rc"
    echo "task_${task}_log=$log"

    if [[ "$rc" -ne 0 ]]; then
        summary \
            "TASK_${task}_FAILED | rc=$rc | log=$log"

        echo
        echo "===== FAILURE LOG ====="
        echo "$log"
        echo

        exit "$rc"
    fi

    summary \
        "TASK_${task}_PASS | log=$log"
}


gate_for_task() {
    local task="$1"

    case "$task" in
        13)
            printf '%s\n' \
                "scripts/sandbox-tasks/13-evidence.sh"
            ;;

        14)
            printf '%s\n' \
                "scripts/sandbox-tasks/14-network-policy.sh"
            ;;

        15)
            printf '%s\n' \
                "scripts/sandbox-tasks/15-harness.sh"
            ;;

        16)
            printf '%s\n' \
                "scripts/sandbox-tasks/16-pro-layer.sh"
            ;;

        17)
            printf '%s\n' \
                "scripts/sandbox-tasks/17-data-engine.sh"
            ;;

        18)
            printf '%s\n' \
                "scripts/sandbox-tasks/18-production-matrix.sh"
            ;;

        *)
            return 1
            ;;
    esac
}


# ------------------------------------------------------------
# Selective Git ownership by task
# ------------------------------------------------------------

task_paths() {
    local task="$1"

    case "$task" in

        13)
            cat <<'EOF'
engine/sandbox/evidence
engine/sandbox/lifecycle/timeout.py
tests/sandbox/test_evidence_real.py
tests/sandbox/test_firecracker_guest_real.py
scripts/sandbox-tasks/13-evidence.sh
EOF
            ;;

        14)
            cat <<'EOF'
engine/sandbox/policy/network.py
tests/sandbox/test_network_policy_real.py
scripts/sandbox-tasks/14-network-policy.sh
EOF
            ;;

        15)
            cat <<'EOF'
engine/sandbox/agentic_harness.py
scripts/sandbox-tasks/15-harness.sh
EOF
            ;;

        16)
            cat <<'EOF'
engine/sandbox/pro_layer.py
tests/sandbox/test_pro_layer_real.py
scripts/sandbox-tasks/16-pro-layer.sh
EOF
            ;;

        17)
            cat <<'EOF'
engine/sandbox/data_engine.py
tests/sandbox/test_data_engine_integration_real.py
scripts/sandbox-tasks/17-data-engine.sh
EOF
            ;;

        18)
            cat <<'EOF'
tests/sandbox/test_sandbox_adversarial_real.py
scripts/sandbox-tasks/18-production-matrix.sh
EOF
            ;;

        19)
            cat <<'EOF'
scripts/sandbox-tasks/complete-sandbox-13-19.sh
EOF
            ;;

        *)
            return 1
            ;;
    esac
}


task_commit_message() {
    local task="$1"

    case "$task" in
        13)
            printf '%s\n' \
                "sandbox: complete evidence integrity and execution records (Task 13)"
            ;;

        14)
            printf '%s\n' \
                "sandbox: complete network isolation policy (Task 14)"
            ;;

        15)
            printf '%s\n' \
                "sandbox: integrate Agentic Harness boundary (Task 15)"
            ;;

        16)
            printf '%s\n' \
                "sandbox: integrate Pro Layer governance (Task 16)"
            ;;

        17)
            printf '%s\n' \
                "sandbox: integrate Data Engine persistence (Task 17)"
            ;;

        18)
            printf '%s\n' \
                "sandbox: complete production adversarial matrix (Task 18)"
            ;;

        19)
            printf '%s\n' \
                "sandbox: complete production sandbox verification (Task 19)"
            ;;

        *)
            return 1
            ;;
    esac
}


stage_task() {
    local task="$1"
    local path
    local found=0

    require_no_preexisting_stage

    echo
    echo "===== TASK $task SELECTIVE STAGE ====="

    while IFS= read -r path; do
        [[ -n "$path" ]] || continue

        if [[ -e "$path" ]] \
            || git ls-files \
                --error-unmatch \
                "$path" \
                >/dev/null 2>&1
        then
            git add -- "$path"
            found=1
        else
            echo \
                "INFO: Task $task path currently absent: $path"
        fi
    done < <(
        task_paths "$task"
    )

    if [[ "$found" -eq 0 ]]; then
        echo \
            "INFO: Task $task has no files available for staging"
    fi

    echo
    echo "===== STAGED FILES ====="

    git diff --cached --name-status

    echo
    echo "===== STAGED DIFF CHECK ====="

    git diff --cached --check

    echo "TASK_${task}_SELECTIVE_STAGE_OK"
}


commit_task() {
    local task="$1"
    local message

    message="$(
        task_commit_message "$task"
    )"

    if git diff --cached --quiet; then
        echo
        echo \
            "INFO: Task $task has no new staged delta; no commit required"

        return 0
    fi

    echo
    echo "===== COMMIT TASK $task ====="

    git commit \
        -m "$message"

    echo
    echo "task_${task}_commit=$(git rev-parse HEAD)"

    git log \
        -1 \
        --oneline

    summary \
        "TASK_${task}_COMMITTED | $(git rev-parse HEAD)"
}


push_task() {
    local task="$1"

    echo
    echo "===== PUSH TASK $task ====="

    git push \
        "$REMOTE" \
        "$EXPECTED_BRANCH"

    verify_remote_head "$task"
}


close_task() {
    local task="$1"

    stage_task "$task"

    commit_task "$task"

    push_task "$task"

    summary \
        "TASK_${task}_CLOSED"

    echo
    echo "======================================"
    echo "TASK $task CLOSED"
    echo "======================================"
}


# ------------------------------------------------------------
# Task 13 — Evidence
# ------------------------------------------------------------

task_13() {
    local gate

    gate="$(
        gate_for_task 13
    )"

    echo "===== TASK 13 — EVIDENCE ====="

    test -f "$gate"

    bash -n "$gate"

    python -m py_compile \
        engine/sandbox/evidence/*.py \
        engine/sandbox/lifecycle/timeout.py \
        tests/sandbox/test_evidence_real.py

    echo
    echo "===== TASK 13 REAL EVIDENCE TESTS ====="

    python -m pytest -q -s \
        tests/sandbox/test_evidence_real.py

    echo
    echo "===== TASK 12 REGRESSION ====="

    scripts/sandbox-tasks/12-lifecycle.sh

    echo
    echo "===== TASK 13 GATE ====="

    "$gate"

    echo
    echo "TASK13_EVIDENCE_PASS"
}


# ------------------------------------------------------------
# Task 14 — Network Policy
# ------------------------------------------------------------

task_14() {
    local gate

    gate="$(
        gate_for_task 14
    )"

    echo "===== TASK 14 — NETWORK POLICY ====="

    test -f "$gate"

    bash -n "$gate"

    python -m py_compile \
        engine/sandbox/policy/network.py \
        tests/sandbox/test_network_policy_real.py

    echo
    echo "===== TASK 14 REAL TEST ====="

    python -m pytest -q -s \
        tests/sandbox/test_network_policy_real.py

    echo
    echo "===== TASK 14 GATE ====="

    "$gate"

    echo
    echo "TASK14_NETWORK_POLICY_PASS"
}


# ------------------------------------------------------------
# Task 15 — Agentic Harness
# ------------------------------------------------------------

task_15() {
    local gate

    gate="$(
        gate_for_task 15
    )"

    echo "===== TASK 15 — AGENTIC HARNESS ====="

    test -f "$gate"

    bash -n "$gate"

    python -m py_compile \
        engine/sandbox/agentic_harness.py

    echo
    echo "===== TASK 15 GATE ====="

    "$gate"

    echo
    echo "TASK15_AGENTIC_HARNESS_PASS"
}


# ------------------------------------------------------------
# Task 16 — Pro Layer
# ------------------------------------------------------------

task_16() {
    local gate

    gate="$(
        gate_for_task 16
    )"

    echo "===== TASK 16 — PRO LAYER ====="

    test -f "$gate"

    bash -n "$gate"

    python -m py_compile \
        engine/sandbox/pro_layer.py \
        tests/sandbox/test_pro_layer_real.py

    echo
    echo "===== TASK 16 REAL TEST ====="

    python -m pytest -q -s \
        tests/sandbox/test_pro_layer_real.py

    echo
    echo "===== TASK 16 GATE ====="

    "$gate"

    echo
    echo "TASK16_PRO_LAYER_PASS"
}


# ------------------------------------------------------------
# Task 17 — Data Engine
# ------------------------------------------------------------

task_17() {
    local gate

    gate="$(
        gate_for_task 17
    )"

    echo "===== TASK 17 — DATA ENGINE ====="

    test -f "$gate"

    bash -n "$gate"

    python -m py_compile \
        engine/sandbox/data_engine.py \
        tests/sandbox/test_data_engine_integration_real.py

    echo
    echo "===== TASK 17 REAL TEST ====="

    python -m pytest -q -s \
        tests/sandbox/test_data_engine_integration_real.py

    echo
    echo "===== TASK 17 GATE ====="

    "$gate"

    echo
    echo "TASK17_DATA_ENGINE_PASS"
}


# ------------------------------------------------------------
# Task 18 — Production / Adversarial Matrix
# ------------------------------------------------------------

task_18() {
    local gate

    gate="$(
        gate_for_task 18
    )"

    echo "===== TASK 18 — PRODUCTION MATRIX ====="

    test -f "$gate"

    bash -n "$gate"

    python -m py_compile \
        tests/sandbox/test_sandbox_adversarial_real.py

    echo
    echo "===== TASK 18 ADVERSARIAL TEST ====="

    python -m pytest -q -s \
        tests/sandbox/test_sandbox_adversarial_real.py

    echo
    echo "===== TASK 18 GATE ====="

    "$gate"

    echo
    echo "TASK18_PRODUCTION_MATRIX_PASS"
}


# ------------------------------------------------------------
# Task 19 — Complete Sandbox
# ------------------------------------------------------------

task_19() {
    local task

    echo "===== TASK 19 — COMPLETE SANDBOX ====="

    echo
    echo "===== RE-RUN TASK GATES ====="

    scripts/sandbox-tasks/12-lifecycle.sh

    for task in 13 14 15 16 17 18; do
        gate="$(
            gate_for_task "$task"
        )"

        echo
        echo "----- Task $task final gate -----"

        "$gate"
    done

    echo
    echo "===== COMPLETE SANDBOX COMPILE ====="

    python -m compileall -q \
        engine/sandbox \
        tests/sandbox

    echo "SANDBOX_COMPILE_ALL_OK"

    echo
    echo "===== NO MOCK / FAKE TESTS ====="

    forbidden="$(
        grep -RInE \
            'unittest\.mock|MagicMock|Mock\(|monkeypatch' \
            tests/sandbox \
            --include='test_*.py' \
            || true
    )"

    if [[ -n "$forbidden" ]]; then
        echo "FAIL: mock/fake Sandbox tests detected"
        printf '%s\n' "$forbidden"
        return 1
    fi

    echo "SANDBOX_REAL_TESTS_ONLY_OK"

    echo
    echo "===== COMPLETE REAL SANDBOX TEST SUITE ====="

    python -m pytest -q -s \
        tests/sandbox

    echo
    echo "SANDBOX_REAL_TEST_SUITE_OK"

    echo
    echo "===== SANDBOX RUNTIME RESIDUE ====="

    residue=0

    podman_residue="$(
        podman ps -a \
            --format '{{.Names}}' \
            2>/dev/null \
            | grep '^dataworc-podman-' \
            || true
    )"

    if [[ -n "$podman_residue" ]]; then
        echo "FAIL: Podman residue"
        printf '%s\n' "$podman_residue"
        residue=1
    fi


    gvisor_residue="$(
        docker ps -a \
            --format '{{.Names}}' \
            2>/dev/null \
            | grep '^dataworc-gvisor-' \
            || true
    )"

    if [[ -n "$gvisor_residue" ]]; then
        echo "FAIL: gVisor residue"
        printf '%s\n' "$gvisor_residue"
        residue=1
    fi


    incus_residue="$(
        incus list \
            --format=csv \
            -c n \
            2>/dev/null \
            | grep -E '^dataworc-(sandbox|vm)-' \
            || true
    )"

    if [[ -n "$incus_residue" ]]; then
        echo "FAIL: Incus residue"
        printf '%s\n' "$incus_residue"
        residue=1
    fi


    qemu_residue="$(
        pgrep -af \
            'qemu-system.*dataworc-qemu-' \
            || true
    )"

    if [[ -n "$qemu_residue" ]]; then
        echo "FAIL: QEMU residue"
        printf '%s\n' "$qemu_residue"
        residue=1
    fi


    firecracker_residue="$(
        pgrep -af \
            'firecracker.*dataworc-' \
            || true
    )"

    if [[ -n "$firecracker_residue" ]]; then
        echo "FAIL: Firecracker residue"
        printf '%s\n' "$firecracker_residue"
        residue=1
    fi


    scope_residue="$(
        systemctl --user \
            list-units \
            --type=scope \
            --all \
            --no-legend \
            'dataworc-sandbox-*.scope' \
            2>/dev/null \
            | grep 'dataworc-sandbox-' \
            || true
    )"

    if [[ -n "$scope_residue" ]]; then
        echo "FAIL: systemd Sandbox scope residue"
        printf '%s\n' "$scope_residue"
        residue=1
    fi


    if [[ "$residue" -ne 0 ]]; then
        return 1
    fi

    echo "SANDBOX_RUNTIME_RESIDUE_CLEAN"

    echo
    echo "======================================"
    echo "TASK19_SANDBOX_COMPLETE_PASS"
    echo "======================================"
}


task_body() {
    local task="$1"

    case "$task" in
        13)
            task_13
            ;;

        14)
            task_14
            ;;

        15)
            task_15
            ;;

        16)
            task_16
            ;;

        17)
            task_17
            ;;

        18)
            task_18
            ;;

        19)
            task_19
            ;;

        *)
            echo \
                "FAIL: unsupported task $task"

            return 1
            ;;
    esac
}


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

summary \
    "SANDBOX_COMPLETION_START | session=$SESSION_STAMP"

summary \
    "repo=$ROOT"

summary \
    "starting_head=$(git rev-parse HEAD)"

require_branch

require_no_preexisting_stage


declare -A LABELS=(
    [13]="Evidence"
    [14]="Network Policy"
    [15]="Agentic Harness"
    [16]="Pro Layer"
    [17]="Data Engine Integration"
    [18]="Production Matrix"
    [19]="Final Sandbox Verification"
)


for task in 13 14 15 16 17 18 19; do

    if ! run_logged_task \
        "$task" \
        "${LABELS[$task]}"
    then
        fail \
            "Task $task failed; inspect $LOG_ROOT/task-${task}.log"
    fi

    close_task \
        "$task"

done


FINAL_LOCAL_HEAD="$(
    git rev-parse HEAD
)"

FINAL_REMOTE_HEAD="$(
    remote_head
)"


echo
echo "======================================"
echo "FINAL SANDBOX HEAD"
echo "======================================"
echo "local_head=$FINAL_LOCAL_HEAD"
echo "remote_head=$FINAL_REMOTE_HEAD"


if [[ "$FINAL_LOCAL_HEAD" != "$FINAL_REMOTE_HEAD" ]]; then
    fail \
        "final local and remote HEAD differ"
fi


summary \
    "DATAWORC_SANDBOX_COMPLETE | head=$FINAL_LOCAL_HEAD"


echo
echo "======================================"
echo "DATAWORC_SANDBOX_COMPLETE"
echo "======================================"
echo "head=$FINAL_LOCAL_HEAD"
echo "logs=$LOG_ROOT"
echo "summary=$SUMMARY_LOG"
echo
