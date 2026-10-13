"""Task 09.6: real FirecrackerRuntime tests (KVM, real artifacts, no mocks)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from engine.sandbox.guest_protocol import GuestProtocolError
from engine.sandbox.models import (
    IsolationClass,
    ResourceLimits,
    RuntimeKind,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.firecracker import (
    DEFAULT_PIN_FILE,
    GUEST_FILES,
    REPO_ROOT,
    FirecrackerRuntime,
    FirecrackerRuntimeUnavailable,
    guest_image_dir,
    guest_inputs_digest,
    sha256_file,
)

sys.path.insert(0, str(REPO_ROOT / "scripts" / "sandbox-tasks"))

import firecracker_guest_image as builder  # noqa: E402


def _request(command: list[str], **overrides) -> SandboxRequest:
    limits = overrides.pop(
        "limits",
        ResourceLimits(cpu_count=1, memory_mb=512, timeout_seconds=20, pids=32),
    )
    return SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.UNTRUSTED,
        command=command,
        requires_vm_boundary=True,
        limits=limits,
        **overrides,
    )


def _firecracker_processes() -> str:
    completed = subprocess.run(
        ["pgrep", "-af", "firecracker --id dataworc-fc-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _assert_clean(run_root: Path) -> None:
    leftovers = sorted(run_root.iterdir()) if run_root.exists() else []
    assert leftovers == [], f"run directories left behind: {leftovers}"
    assert _firecracker_processes() == "", "residual Firecracker process"


@pytest.fixture(scope="module")
def artifacts():
    assert os.access("/dev/kvm", os.R_OK | os.W_OK), "/dev/kvm not accessible"
    resolved = FirecrackerRuntime().resolve_artifacts()
    source_sha = sha256_file(resolved.rootfs)

    yield resolved

    assert sha256_file(resolved.rootfs) == source_sha, "verified guest image changed"
    print(f"REAL_FC_SOURCE_IMAGE_UNCHANGED {source_sha}")


@pytest.fixture
def run_root():
    """Short, disk-backed run root.

    pytest tmp_path names are long; the per-VM vsock socket path must fit
    in AF_UNIX's 107 bytes. The runtime must create this directory itself.
    """

    base = Path("~/.cache/dataworc-run").expanduser()
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="fct-", dir=base))
    root.rmdir()

    yield root

    shutil.rmtree(root, ignore_errors=True)


# ----------------------------------------------------------- parity / static


def test_guest_inputs_digest_matches_image_builder() -> None:
    pin = json.loads(DEFAULT_PIN_FILE.read_text())
    base_sha = pin["artifacts"]["rootfs"]["sha256"]
    store = Path(pin["artifacts"]["store"]).expanduser()

    assert GUEST_FILES == tuple(
        (item.repo_path, item.guest_path, item.mode) for item in builder.GUEST_FILES
    )
    assert guest_inputs_digest(base_sha, REPO_ROOT) == builder.inputs_digest(
        base_sha, REPO_ROOT
    )

    digest, _ = guest_inputs_digest(base_sha, REPO_ROOT)
    assert guest_image_dir(store, pin["architecture"], digest) == builder.guest_image_dir(
        store, pin["architecture"], digest
    )


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"network_enabled": True}, ValueError),
        ({"working_directory": Path("/tmp")}, ValueError),
        ({"writable_workspace": True}, ValueError),
        ({"limits": ResourceLimits(cpu_count=1.5)}, ValueError),
        ({"limits": ResourceLimits(cpu_count=0)}, ValueError),
        ({"limits": ResourceLimits(memory_mb=128)}, ValueError),
        ({"limits": ResourceLimits(timeout_seconds=0)}, ValueError),
        ({"limits": ResourceLimits(pids=0)}, GuestProtocolError),
        ({"command": []}, GuestProtocolError),
        ({"environment": {"A": "x\x00"}}, GuestProtocolError),
    ],
)
def test_invalid_requests_rejected_before_boot(overrides, error, run_root: Path) -> None:
    overrides = dict(overrides)
    command = overrides.pop("command", ["/bin/true"])
    runtime = FirecrackerRuntime(run_root=run_root)

    with pytest.raises(error):
        runtime.execute(_request(command, **overrides))

    assert not run_root.exists(), "a run directory was created before validation"
    assert _firecracker_processes() == ""


# ------------------------------------------------------------ real boots


def test_real_execution(artifacts, run_root: Path) -> None:
    runtime = FirecrackerRuntime(run_root=run_root)
    result = runtime.execute(
        _request(
            [
                "/bin/sh",
                "-c",
                "echo FC_RUNTIME_OK; echo FC_STDERR >&2; "
                "ls /sys/class/net | sort | tr '\\n' ' '; echo; "
                "nproc; systemd-detect-virt || true; "
                "cg=/sys/fs/cgroup$(grep '^0::' /proc/self/cgroup | cut -d: -f3-); "
                "cat $cg/pids.max; "
                'printf "%s|%s\\n" "$FC_MARKER" "$HOME"; '
                "exit 7",
            ],
            environment={"FC_MARKER": "fc-env-ok"},
        )
    )

    print(result)

    assert result.runtime_kind == RuntimeKind.FIRECRACKER
    assert result.isolation_class == IsolationClass.HARDWARE
    assert result.exit_code == 7
    assert result.timed_out is False
    assert "FC_STDERR" in result.stderr

    lines = [line.strip() for line in result.stdout.splitlines()]
    start = lines.index("FC_RUNTIME_OK")

    assert lines[start + 1].split() == ["lo"]
    assert lines[start + 2] == "1"
    assert lines[start + 3] == "kvm"
    assert lines[start + 4] == "32"
    assert lines[start + 5] == "fc-env-ok|/root"

    _assert_clean(run_root)
    print("REAL_FC_RUNTIME_EXECUTION_OK")


def test_real_timeout_kills_vm(artifacts, run_root: Path) -> None:
    runtime = FirecrackerRuntime(run_root=run_root)
    result = runtime.execute(
        _request(
            ["/bin/sh", "-c", "sleep 30"],
            limits=ResourceLimits(cpu_count=1, memory_mb=512, timeout_seconds=3, pids=16),
        )
    )

    print(result)

    assert result.exit_code == 124
    assert result.timed_out is True
    assert 3 <= result.duration_seconds < 8

    _assert_clean(run_root)
    print("REAL_FC_RUNTIME_TIMEOUT_OK")


def test_real_result_size_is_capped(artifacts, run_root: Path) -> None:
    runtime = FirecrackerRuntime(run_root=run_root, max_result_bytes=64 * 1024)
    result = runtime.execute(
        _request(["/bin/sh", "-c", "head -c 200000 /dev/zero | tr '\\0' a"])
    )

    assert result.exit_code == 125
    assert "exceeds 65536 bytes" in result.stderr
    assert result.stdout == ""

    _assert_clean(run_root)
    print("REAL_FC_RUNTIME_SIZE_CAP_OK")


def test_real_sequential_runs_are_disposable(artifacts, run_root: Path) -> None:
    runtime = FirecrackerRuntime(run_root=run_root)
    marker = "/root/dataworc-disposable-marker"

    first = runtime.execute(
        _request(["/bin/sh", "-c", f"test ! -e {marker} && touch {marker} && echo created"])
    )
    second = runtime.execute(
        _request(["/bin/sh", "-c", f"test -e {marker} && echo persisted || echo fresh"])
    )

    assert (first.exit_code, first.stdout.strip()) == (0, "created")
    assert (second.exit_code, second.stdout.strip()) == (0, "fresh")

    _assert_clean(run_root)
    print("REAL_FC_RUNTIME_DISPOSABLE_OK")


# ------------------------------------------------- integrity before boot


def _image_copy(artifacts, tmp_path: Path, *, copy_rootfs: bool) -> Path:
    target = tmp_path / "guest-image"
    target.mkdir()
    shutil.copyfile(artifacts.guest_image_dir / "manifest.json", target / "manifest.json")
    rootfs = target / artifacts.rootfs.name

    if copy_rootfs:
        shutil.copyfile(artifacts.rootfs, rootfs)
    else:
        try:
            os.link(artifacts.rootfs, rootfs)
        except OSError:
            shutil.copyfile(artifacts.rootfs, rootfs)
            os.chmod(rootfs, 0o444)

    return target


def test_tampered_rootfs_is_refused_before_boot(artifacts, tmp_path: Path, run_root: Path) -> None:
    image = _image_copy(artifacts, tmp_path, copy_rootfs=True)
    rootfs = image / artifacts.rootfs.name
    os.chmod(rootfs, 0o644)

    with rootfs.open("r+b") as handle:
        handle.seek(4096)
        original = handle.read(1)
        handle.seek(4096)
        handle.write(bytes([original[0] ^ 0xFF]))

    os.chmod(rootfs, 0o444)
    runtime = FirecrackerRuntime(run_root=run_root, guest_image_override=image)

    with pytest.raises(FirecrackerRuntimeUnavailable, match="differs from its manifest"):
        runtime.execute(_request(["/bin/true"]))

    _assert_clean(run_root)


def test_stale_manifest_is_refused(artifacts, tmp_path: Path, run_root: Path) -> None:
    image = _image_copy(artifacts, tmp_path, copy_rootfs=False)
    manifest_path = image / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["inputs_sha256"] = "0" * 64
    os.chmod(manifest_path, 0o644)
    manifest_path.write_text(json.dumps(manifest))

    runtime = FirecrackerRuntime(run_root=run_root, guest_image_override=image)

    with pytest.raises(FirecrackerRuntimeUnavailable, match="stale"):
        runtime.execute(_request(["/bin/true"]))

    assert not run_root.exists()


def test_writable_rootfs_is_refused(artifacts, tmp_path: Path, run_root: Path) -> None:
    image = _image_copy(artifacts, tmp_path, copy_rootfs=True)
    os.chmod(image / artifacts.rootfs.name, 0o644)

    runtime = FirecrackerRuntime(run_root=run_root, guest_image_override=image)

    with pytest.raises(FirecrackerRuntimeUnavailable, match="writable"):
        runtime.execute(_request(["/bin/true"]))

    assert not run_root.exists()


def test_boot_failure_reports_serial_console_and_cleans_up(
    artifacts, tmp_path: Path, run_root: Path
) -> None:
    runtime = FirecrackerRuntime(run_root=run_root, boot_timeout_seconds=0.3)
    started = time.monotonic()

    with pytest.raises(FirecrackerRuntimeUnavailable, match="not ready within 0.3s"):
        runtime.execute(_request(["/bin/true"]))

    assert time.monotonic() - started < 15
    _assert_clean(run_root)
    print("REAL_FC_RUNTIME_BOOT_FAILURE_CLEANUP_OK")
