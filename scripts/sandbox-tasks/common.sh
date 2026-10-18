#!/usr/bin/env bash

set -Eeuo pipefail

export ROOT="${HOME}/Data-Platform-worktrees/sandbox-podman"
export VENV="${HOME}/Data-Platform/venv/bin/activate"

cd "$ROOT"

if [[ -f "$VENV" ]]; then
    # shellcheck disable=SC1090
    source "$VENV"
fi

section() {
    printf '\n============================================================\n'
    printf '%s\n' "$1"
    printf '============================================================\n'
}

pass() {
    printf 'PASS: %s\n' "$1"
}

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

require_file() {
    [[ -f "$1" ]] || fail "Missing file: $1"
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

no_mocks() {
    if grep -RInE \
        'unittest\.mock|MagicMock|@patch|patch\.object|monkeypatch|Fake[A-Z]|Mock[A-Z]' \
        tests/sandbox \
        --include='test_*.py'
    then
        fail "Mock/fake sandbox tests detected"
    fi

    pass "No mock/fake tests"
}

compile_sandbox() {
    python -m compileall -q engine/sandbox tests/sandbox
    pass "Sandbox compilation"
}

check_kvm() {
    [[ -e /dev/kvm ]] || fail "/dev/kvm missing"
    [[ -r /dev/kvm ]] || fail "/dev/kvm not readable"
    [[ -w /dev/kvm ]] || fail "/dev/kvm not writable"

    pass "KVM access"
}

check_cleanup() {
    if command -v podman >/dev/null 2>&1; then
        PODMAN_LEFT="$(
            podman ps -a \
                --filter name=dataworc-sandbox- \
                --format '{{.Names}}' \
                2>/dev/null || true
        )"

        [[ -z "$PODMAN_LEFT" ]] || {
            echo "$PODMAN_LEFT"
            fail "Residual Podman sandboxes"
        }
    fi

    if command -v docker >/dev/null 2>&1; then
        DOCKER_LEFT="$(
            docker ps -a \
                --filter name=dataworc-gvisor- \
                --format '{{.Names}}' \
                2>/dev/null || true
        )"

        [[ -z "$DOCKER_LEFT" ]] || {
            echo "$DOCKER_LEFT"
            fail "Residual gVisor containers"
        }
    fi

    if command -v incus >/dev/null 2>&1; then
        INCUS_LEFT="$(
            incus list --format csv -c n 2>/dev/null \
            | grep '^dataworc-sandbox-' || true
        )"

        [[ -z "$INCUS_LEFT" ]] || {
            echo "$INCUS_LEFT"
            fail "Residual Incus instances"
        }
    fi

    pass "Runtime cleanup"
}
