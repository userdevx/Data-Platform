"""Task 09.7: real Firecracker matrix (KVM, real artifacts, no mocks).

Covers what 09.6 did not: guest-kernel isolation, concurrent VMs, vCPU and
memory limits, host-process death mid-run (SIGTERM/SIGKILL) with crash
recovery, rootfs copy failure, and a measured timing baseline.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path

import pytest

from engine.sandbox.models import (
    ResourceLimits,
    SandboxRequest,
    TrustLevel,
    WorkloadType,
)
from engine.sandbox.runtime.firecracker import (
    DEFAULT_PIN_FILE,
    OWNER_FILE,
    REPO_ROOT,
    RUN_DIR_PREFIX,
    FirecrackerRuntime,
    process_start_time,
    sha256_file,
)


def _request(command: list[str], **limits) -> SandboxRequest:
    values = dict(cpu_count=1, memory_mb=512, timeout_seconds=30, pids=32)
    values.update(limits)
    return SandboxRequest(
        workload_type=WorkloadType.SYSTEM,
        trust_level=TrustLevel.UNTRUSTED,
        command=command,
        requires_vm_boundary=True,
        limits=ResourceLimits(**values),
    )


def _vm_processes() -> str:
    completed = subprocess.run(
        ["pgrep", "-af", "firecracker --id dataworc-fc-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _vm_processes_for(run_root: Path) -> str:
    return "\n".join(
        line for line in _vm_processes().splitlines() if str(run_root) in line
    )


def _assert_clean(run_root: Path) -> None:
    leftovers = sorted(run_root.iterdir()) if run_root.exists() else []
    assert leftovers == [], f"run directories left behind: {leftovers}"
    assert _vm_processes_for(run_root) == "", "residual Firecracker process"


@pytest.fixture(scope="module")
def artifacts():
    assert os.access("/dev/kvm", os.R_OK | os.W_OK), "/dev/kvm not accessible"
    resolved = FirecrackerRuntime().resolve_artifacts()
    source_sha = sha256_file(resolved.rootfs)

    yield resolved

    assert sha256_file(resolved.rootfs) == source_sha, "verified guest image changed"
    print(f"REAL_FC_MATRIX_SOURCE_IMAGE_UNCHANGED {source_sha}")


@pytest.fixture
def run_root():
    """Short, disk-backed run root (AF_UNIX path limit); created by the runtime."""

    base = Path("~/.cache/dataworc-run").expanduser()
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="fcm-", dir=base))
    root.rmdir()

    yield root

    shutil.rmtree(root, ignore_errors=True)


def _timed(runtime: FirecrackerRuntime, request: SandboxRequest):
    started = time.monotonic()
    result = runtime.execute(request)
    return result, time.monotonic() - started


# ------------------------------------------------------- crash recovery unit


def test_sweep_keeps_live_owner_and_removes_dead_owner(run_root: Path) -> None:
    run_root.mkdir()

    live = run_root / f"{RUN_DIR_PREFIX}live"
    dead = run_root / f"{RUN_DIR_PREFIX}dead"
    unowned = run_root / f"{RUN_DIR_PREFIX}unowned"

    for directory in (live, dead, unowned):
        directory.mkdir()

    live.joinpath(OWNER_FILE).write_text(f"{os.getpid()} {process_start_time(os.getpid())}\n")

    child = subprocess.Popen(["sleep", "30"])
    dead.joinpath(OWNER_FILE).write_text(f"{child.pid} {process_start_time(child.pid)}\n")
    child.kill()
    child.wait()

    removed = FirecrackerRuntime(run_root=run_root).sweep_stale_runs()

    assert removed == [dead]
    assert live.is_dir() and unowned.is_dir() and not dead.exists()
    print("REAL_FC_SWEEP_OWNERSHIP_OK")


# ------------------------------------------------------------- isolation


def test_guest_kernel_is_isolated_from_host(artifacts, run_root: Path) -> None:
    pin = json.loads(DEFAULT_PIN_FILE.read_text())
    host_release = os.uname().release
    host_boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    host_domain = Path("/proc/sys/kernel/domainname").read_text().strip()

    result = FirecrackerRuntime(run_root=run_root).execute(
        _request(
            [
                "/bin/sh",
                "-c",
                "uname -r; cat /proc/sys/kernel/random/boot_id; "
                "echo dataworc-guest-only > /proc/sys/kernel/domainname; "
                "cat /proc/sys/kernel/domainname",
            ]
        )
    )

    assert result.exit_code == 0, result.stderr
    guest_release, guest_boot_id, guest_domain = result.stdout.split()

    assert guest_release.startswith(pin["artifacts"]["kernel_version"])
    assert guest_release != host_release
    assert guest_boot_id != host_boot_id
    assert guest_domain == "dataworc-guest-only"
    assert Path("/proc/sys/kernel/domainname").read_text().strip() == host_domain

    _assert_clean(run_root)
    print(
        f"REAL_FC_KERNEL_ISOLATION_OK guest={guest_release} host={host_release} "
        "boot_id differs; guest kernel setting invisible on host"
    )


def test_two_concurrent_vms(artifacts, run_root: Path) -> None:
    outcomes: dict[int, tuple] = {}
    errors: list[BaseException] = []

    def run(index: int) -> None:
        try:
            outcomes[index] = _timed(
                FirecrackerRuntime(run_root=run_root),
                _request(
                    [
                        "/bin/sh",
                        "-c",
                        f"cat /proc/sys/kernel/random/boot_id; sleep 3; echo VM{index}",
                    ]
                ),
            )
        except BaseException as exc:  # surfaced below
            errors.append(exc)

    started = time.monotonic()
    threads = [threading.Thread(target=run, args=(index,)) for index in (1, 2)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=120)

    elapsed = time.monotonic() - started

    assert not errors, errors
    assert set(outcomes) == {1, 2}

    boot_ids = []

    for index, (result, _) in outcomes.items():
        assert result.exit_code == 0, result.stderr
        boot_id, marker = result.stdout.split()
        assert marker == f"VM{index}"
        boot_ids.append(boot_id)

    sequential = sum(seconds for _, seconds in outcomes.values())

    assert boot_ids[0] != boot_ids[1], "two runs shared one guest kernel"
    assert elapsed < 0.8 * sequential, "runs did not overlap"

    _assert_clean(run_root)
    print(
        f"REAL_FC_CONCURRENT_OK wall={elapsed:.2f}s "
        f"sum_of_runs={sequential:.2f}s distinct guest kernels"
    )


# ------------------------------------------------------------- resources


def test_two_vcpus(artifacts, run_root: Path) -> None:
    result = FirecrackerRuntime(run_root=run_root).execute(
        _request(["nproc"], cpu_count=2)
    )

    assert (result.exit_code, result.stdout.strip()) == (0, "2")
    _assert_clean(run_root)
    print("REAL_FC_TWO_VCPUS_OK")


def test_minimum_memory_boots(artifacts, run_root: Path) -> None:
    result = FirecrackerRuntime(run_root=run_root).execute(
        _request(["awk", "/MemTotal/ {print $2}", "/proc/meminfo"], memory_mb=256)
    )

    assert result.exit_code == 0, result.stderr
    mem_kib = int(result.stdout.strip())

    assert 0 < mem_kib <= 256 * 1024
    _assert_clean(run_root)
    print(f"REAL_FC_MEMORY_FLOOR_256_OK MemTotal={mem_kib} KiB")


# --------------------------------------------- host process death mid-run

_VICTIM = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from engine.sandbox.models import ResourceLimits, SandboxRequest, TrustLevel, WorkloadType
    from engine.sandbox.runtime.firecracker import FirecrackerRuntime

    FirecrackerRuntime(run_root=Path(sys.argv[1])).execute(
        SandboxRequest(
            workload_type=WorkloadType.SYSTEM,
            trust_level=TrustLevel.UNTRUSTED,
            command=["sleep", "120"],
            requires_vm_boundary=True,
            limits=ResourceLimits(cpu_count=1, memory_mb=512, timeout_seconds=110, pids=16),
        )
    )
    """
)


@pytest.mark.parametrize("host_signal", [signal.SIGTERM, signal.SIGKILL])
def test_host_death_mid_run_kills_vm_and_is_recovered(
    artifacts, run_root: Path, host_signal: signal.Signals
) -> None:
    host = subprocess.Popen(
        [sys.executable, "-c", _VICTIM, str(run_root)],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )

    try:
        deadline = time.monotonic() + 90

        while not list(run_root.glob(f"{RUN_DIR_PREFIX}*/vsock.sock")):
            assert host.poll() is None, "host runtime exited before the VM started"
            assert time.monotonic() < deadline, "VM never started"
            time.sleep(0.1)

        time.sleep(3)  # workload is running inside the guest
        assert _vm_processes_for(run_root), "no VM to orphan"
        [run_dir] = list(run_root.glob(f"{RUN_DIR_PREFIX}*"))

        host.send_signal(host_signal)
        host.wait(timeout=10)
    finally:
        if host.poll() is None:
            host.kill()
            host.wait()

    deadline = time.monotonic() + 10

    while _vm_processes_for(run_root) and time.monotonic() < deadline:
        time.sleep(0.1)

    assert _vm_processes_for(run_root) == "", "VM outlived its host process"
    assert run_dir.is_dir(), "expected the dead owner's run directory before recovery"

    removed = FirecrackerRuntime(run_root=run_root).sweep_stale_runs()

    assert removed == [run_dir]
    _assert_clean(run_root)
    print(f"REAL_FC_HOST_{host_signal.name}_VM_KILLED_AND_RECOVERED_OK")


# ------------------------------------------------------- copy failure


_COPY_FAILURE = textwrap.dedent(
    """
    import errno, resource, sys
    from pathlib import Path
    from engine.sandbox.models import SandboxRequest, TrustLevel, WorkloadType
    from engine.sandbox.runtime.firecracker import FirecrackerRuntime

    limit = 64 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))

    try:
        FirecrackerRuntime(run_root=Path(sys.argv[1])).execute(
            SandboxRequest(
                workload_type=WorkloadType.SYSTEM,
                trust_level=TrustLevel.UNTRUSTED,
                command=["true"],
                requires_vm_boundary=True,
            )
        )
    except OSError as exc:
        print(f"COPY_FAILED errno={errno.errorcode.get(exc.errno)}")
    else:
        print("UNEXPECTED_SUCCESS")
    """
)


def test_rootfs_copy_failure_cleans_up(artifacts, run_root: Path) -> None:
    assert artifacts.rootfs.stat().st_size > 64 * 1024 * 1024

    completed = subprocess.run(
        [sys.executable, "-c", _COPY_FAILURE, str(run_root)],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.stdout.strip() == "COPY_FAILED errno=EFBIG", (
        completed.stdout + completed.stderr
    )
    _assert_clean(run_root)
    print("REAL_FC_COPY_FAILURE_CLEANUP_OK")


# ------------------------------------------------------- timing baseline


def test_timing_baseline(artifacts, run_root: Path) -> None:
    """Measured, not asserted against external figures. Recorded for 18a."""

    copy_target = run_root.parent / f"{run_root.name}-copy.ext4"
    started = time.monotonic()
    shutil.copyfile(artifacts.rootfs, copy_target)
    copy_seconds = time.monotonic() - started
    copy_target.unlink()

    runtime = FirecrackerRuntime(run_root=run_root)
    samples = [_timed(runtime, _request(["true"])) for _ in range(3)]

    for result, _ in samples:
        assert result.exit_code == 0

    totals = sorted(seconds for _, seconds in samples)
    workloads = sorted(result.duration_seconds for result, _ in samples)
    size_mib = artifacts.rootfs.stat().st_size / (1024 * 1024)

    _assert_clean(run_root)
    print(
        "REAL_FC_TIMING_BASELINE "
        f"rootfs={size_mib:.0f}MiB plain_copy={copy_seconds:.2f}s "
        f"end_to_end_median={totals[1]:.2f}s "
        f"(min={totals[0]:.2f}s max={totals[2]:.2f}s) "
        f"workload_median={workloads[1]:.3f}s"
    )
