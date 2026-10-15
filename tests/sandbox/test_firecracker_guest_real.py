from __future__ import annotations

import importlib.util
import json
import re
import time
import os
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from engine.sandbox.guest_protocol import (
    PROTOCOL_VERSION,
    GuestProtocolError,
    build_execute_request,
    decode_message,
    encode_message,
    parse_execution_result,
    validate_ready,
)


REPO = (
    Path(__file__)
    .resolve()
    .parents[2]
)

sys.path.insert(
    0,
    str(
        REPO
        / "scripts"
        / "sandbox-tasks"
    ),
)

from firecracker_guest_image import (  # noqa: E402
    GUEST_FILES,
    build_image,
    stat_inode,
    verify_image,
)

from firecracker_pins import (  # noqa: E402
    PinError,
    sha256_file,
)


def _load_guest_exec():
    path = (
        REPO
        / "engine"
        / "sandbox"
        / "images"
        / "guest"
        / "dataworc_guest_exec.py"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            "dataworc_guest_exec",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "unable to load guest exec module"
        )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    spec.loader.exec_module(
        module
    )

    return module


guest = _load_guest_exec()


def _request(
    **overrides,
) -> dict:
    fields = dict(
        request_id="req-1",
        command=[
            "sh",
            "-c",
            (
                "echo out; "
                "echo err >&2; "
                "exit 3"
            ),
        ],
        environment={},
        working_directory=None,
        pids=16,
    )

    fields.update(
        overrides
    )

    return build_execute_request(
        **fields
    )


def _pin() -> dict:
    return json.loads(
        (
            REPO
            / "engine"
            / "sandbox"
            / "images"
            / "firecracker"
            / "pinned.json"
        ).read_text()
    )


def test_guest_and_host_speak_same_protocol() -> None:
    assert (
        guest.PROTOCOL_VERSION
        == PROTOCOL_VERSION
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {
            "command": [
                "printf",
                "",
            ],
        },
        {
            "environment": {
                "A": "1",
                "LONG_NAME": "x y z",
            },
        },
        {
            "working_directory": "/tmp",
        },
        {
            "pids": 1,
        },
    ],
)
def test_host_built_request_is_valid_in_guest(
    overrides,
) -> None:
    request = _request(
        **overrides
    )

    assert (
        guest.validate_request(request)
        is None
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(
            command=[]
        ),
        lambda r: r.update(
            command=[
                "sh",
                "-c",
                "a\x00b",
            ]
        ),
        lambda r: r.update(
            command="echo hi"
        ),
        lambda r: r.update(
            environment={
                "A=B": "x",
            }
        ),
        lambda r: r.update(
            environment={
                "A": "x\x00",
            }
        ),
        lambda r: r.update(
            environment={
                "A": 1,
            }
        ),
        lambda r: r.update(
            pids=0
        ),
        lambda r: r.update(
            pids=True
        ),
        lambda r: r.update(
            working_directory=""
        ),
        lambda r: r.update(
            id=""
        ),
        lambda r: r.update(
            protocol=(
                PROTOCOL_VERSION
                + 1
            )
        ),
        lambda r: r.update(
            type="shell"
        ),
    ],
)
def test_guest_rejects_invalid_requests(
    mutate,
) -> None:
    request = _request()
    mutate(request)

    error = guest.validate_request(
        request
    )

    assert error is not None

    result = guest.execute_request(
        request,
        use_systemd=False,
    )

    assert (
        result["exit_code"]
        == guest.PROTOCOL_FAILURE_EXIT_CODE
    )

    assert result["stdout"] == ""


def test_real_execution_output_and_exit_code() -> None:
    result = guest.execute_request(
        _request(),
        use_systemd=False,
    )

    parsed = parse_execution_result(
        result,
        expected_request_id="req-1",
    )

    assert parsed.exit_code == 3
    assert parsed.stdout == "out\n"
    assert parsed.stderr == "err\n"


def test_real_execution_environment_and_cwd(
    tmp_path: Path,
) -> None:
    result = guest.execute_request(
        _request(
            command=[
                "sh",
                "-c",
                (
                    'printf "%s|%s" '
                    '"$MARKER" "$(pwd)"'
                ),
            ],
            environment={
                "MARKER": "guest-env-ok",
            },
            working_directory=str(
                tmp_path
            ),
        ),
        use_systemd=False,
    )

    assert result["exit_code"] == 0

    assert result["stdout"] == (
        "guest-env-ok|"
        f"{tmp_path}"
    )


def test_systemd_command_uses_scope_without_dbus() -> None:
    request = _request(
        environment={"A": "1"},
        working_directory="/work",
        pids=32,
    )
    argv = guest.build_command(request)

    assert argv[:3] == ["/usr/bin/systemd-run", "--quiet", "--scope"]
    assert f"--unit={guest.scope_unit_name('req-1')}" in argv
    assert "--property=TasksMax=32" in argv

    # --wait/--pipe need a D-Bus system bus; minimal guests have none.
    for needs_dbus in ("--wait", "--pipe"):
        assert needs_dbus not in argv

    # Environment and cwd are applied to the process, not via systemd.
    assert not any(arg.startswith(("--setenv", "--working-directory")) for arg in argv)

    assert argv[argv.index("--") + 1:] == [
        "sh",
        "-c",
        "echo out; echo err >&2; exit 3",
    ]


@pytest.mark.parametrize(
    "request_id",
    ["req-1", "a/b c", "x" * 200, "../../etc", "\u00e9t\u00e9"],
)
def test_scope_unit_name_is_valid_and_unique(request_id: str) -> None:
    name = guest.scope_unit_name(request_id)

    assert re.fullmatch(r"dataworc-run-[A-Za-z0-9_-]{1,32}-[0-9a-f]{12}", name)
    assert name != guest.scope_unit_name(request_id + "x")


def test_workload_environment_is_base_plus_request_only() -> None:
    marker = "DATAWORC_AGENT_ONLY_VARIABLE"
    os.environ[marker] = "must-not-leak"

    try:
        result = guest.execute_request(
            _request(
                command=[
                    sys.executable,
                    "-c",
                    "import json, os; print(json.dumps(sorted(os.environ)))",
                ],
                environment={"REQUEST_VAR": "1"},
            ),
            use_systemd=False,
        )
    finally:
        del os.environ[marker]

    assert result["exit_code"] == 0, result["stderr"]
    keys = set(json.loads(result["stdout"]))

    assert marker not in keys
    assert {"PATH", "HOME", "LANG", "REQUEST_VAR"} <= keys
    assert keys <= {"PATH", "HOME", "LANG", "REQUEST_VAR", "LC_CTYPE"}


def test_background_children_do_not_hang_or_survive(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    started = time.monotonic()

    result = guest.execute_request(
        _request(command=["sh", "-c", f"sleep 60 & echo $! > {pid_file}; echo done"]),
        use_systemd=False,
    )

    assert result["exit_code"] == 0, result["stderr"]
    assert result["stdout"] == "done\n"
    assert time.monotonic() - started < 15

    child = int(pid_file.read_text())
    deadline = time.monotonic() + 5

    stat_path = Path(f"/proc/{child}/stat")

    while time.monotonic() < deadline:
        try:
            state = (
                stat_path.read_text()
                .rsplit(")", 1)[1]
                .split()[0]
            )
        except (FileNotFoundError, ProcessLookupError):
            break

        if state == "Z":
            break

        time.sleep(0.05)

    try:
        final_state = (
            stat_path.read_text()
            .rsplit(")", 1)[1]
            .split()[0]
        )
    except (FileNotFoundError, ProcessLookupError):
        alive = False
    else:
        alive = final_state != "Z"

    assert not alive, "background child outlived the request"


def test_signal_death_maps_to_shell_convention() -> None:
    result = guest.execute_request(
        _request(command=["sh", "-c", "kill -TERM $$"]),
        use_systemd=False,
    )

    assert result["exit_code"] == 128 + 15


def test_missing_working_directory_is_a_protocol_failure() -> None:
    result = guest.execute_request(
        _request(command=["true"], working_directory="/nonexistent/dataworc"),
        use_systemd=False,
    )

    assert result["exit_code"] == guest.PROTOCOL_FAILURE_EXIT_CODE
    assert "FileNotFoundError" in result["stderr"]


def test_real_stream_session_over_socket() -> None:
    host_end, guest_end = (
        socket.socketpair()
    )

    def serve() -> None:
        with guest_end:
            with guest_end.makefile(
                "rwb",
                buffering=0,
            ) as stream:
                guest.serve_connection(
                    stream,
                    execute=(
                        lambda req:
                        guest.execute_request(
                            req,
                            use_systemd=False,
                        )
                    ),
                )

    thread = threading.Thread(
        target=serve,
        daemon=True,
    )

    thread.start()

    with host_end:
        with host_end.makefile(
            "rwb",
            buffering=0,
        ) as stream:
            validate_ready(
                decode_message(
                    stream.readline()
                )
            )

            stream.write(
                encode_message(
                    _request(
                        request_id="first"
                    )
                )
            )

            first = (
                parse_execution_result(
                    decode_message(
                        stream.readline()
                    ),
                    expected_request_id=(
                        "first"
                    ),
                )
            )

            assert (
                first.exit_code,
                first.stdout,
            ) == (
                3,
                "out\n",
            )

            stream.write(
                b"{not json}\n"
            )

            broken = decode_message(
                stream.readline()
            )

            assert (
                broken["exit_code"]
                == 125
            )

            assert (
                broken["id"]
                is None
            )

            stream.write(
                encode_message(
                    _request(
                        request_id="second",
                        command=[
                            "true"
                        ],
                    )
                )
            )

            second = (
                parse_execution_result(
                    decode_message(
                        stream.readline()
                    ),
                    expected_request_id=(
                        "second"
                    ),
                )
            )

            assert (
                second.exit_code
                == 0
            )

            stream.write(
                encode_message(
                    _request(
                        request_id="third",
                        command=[
                            "true"
                        ],
                    )
                )
            )

            with pytest.raises(
                GuestProtocolError,
                match="does not match",
            ):
                parse_execution_result(
                    decode_message(
                        stream.readline()
                    ),
                    expected_request_id=(
                        "other"
                    ),
                )

    thread.join(
        timeout=5
    )

    assert not thread.is_alive()


@pytest.fixture(scope="module")
def built_image(
    tmp_path_factory,
) -> tuple[
    Path,
    str,
    Path,
]:
    pin = _pin()

    store = Path(
        pin["artifacts"]["store"]
    ).expanduser()

    base = (
        store
        / pin["artifacts"][
            "rootfs"
        ][
            "file"
        ]
    )

    base_sha = (
        pin["artifacts"][
            "rootfs"
        ][
            "sha256"
        ]
    )

    out = (
        tmp_path_factory
        .mktemp("fc-guest")
        / "image"
    )

    build_image(
        base,
        base_sha,
        out,
        REPO,
        provenance={
            "test": True,
            "store": str(store),
        },
    )

    return (
        out,
        base_sha,
        base,
    )


def test_real_build_installs_validated_agent(
    built_image,
) -> None:
    out, base_sha, base = (
        built_image
    )

    manifest = json.loads(
        (
            out
            / "manifest.json"
        ).read_text()
    )

    assert (
        manifest["base"][
            "rootfs_sha256"
        ]
        == base_sha
    )

    assert (
        sha256_file(base)
        == base_sha
    )

    assert (
        manifest["checks"][
            "e2fsck"
        ]
        == "clean"
    )

    assert (
        manifest["checks"][
            "base_rootfs_unchanged"
        ]
        is True
    )

    assert (
        manifest["checks"][
            "derived_rootfs_separate"
        ]
        is True
    )

    assert (
        set(
            manifest["checks"][
                "executables"
            ]
        )
        == {
            "/usr/bin/python3",
            "/usr/bin/systemd-run",
            "/usr/bin/systemctl",
            "/sbin/init",
        }
    )

    rootfs = (
        out
        / "rootfs.ext4"
    )

    assert (
        rootfs.stat().st_mode
        & 0o777
    ) == 0o444

    assert (
        [
            entry["guest_path"]
            for entry
            in manifest["files"]
        ]
        == [
            item.guest_path
            for item
            in GUEST_FILES
        ]
    )

    assert (
        manifest["trust"]["scope"]
        == (
            "derived-build "
            "provenance and "
            "self-consistency"
        )
    )

    assert (
        manifest["trust"][
            "durable_registry"
        ]
        == "Task 11"
    )

    verify_image(
        out,
        base_sha,
        REPO,
    )

    print(
        "REAL_GUEST_IMAGE_OK "
        "executables="
        f"{manifest['checks']['executables']}"
    )


def test_build_refuses_to_overwrite(
    built_image,
) -> None:
    out, base_sha, base = (
        built_image
    )

    with pytest.raises(
        PinError,
        match="already exists",
    ):
        build_image(
            base,
            base_sha,
            out,
            REPO,
            provenance={},
        )


def test_build_rejects_base_directory() -> None:
    pin = _pin()

    store = Path(
        pin["artifacts"]["store"]
    ).expanduser()

    base = (
        store
        / pin["artifacts"][
            "rootfs"
        ][
            "file"
        ]
    )

    base_sha = (
        pin["artifacts"][
            "rootfs"
        ][
            "sha256"
        ]
    )

    with pytest.raises(
        PinError,
        match=(
            "derived guest image directory "
            "must not be the pinned base "
            "rootfs directory"
        ),
    ):
        build_image(
            base,
            base_sha,
            store,
            REPO,
            provenance={},
        )


def test_real_build_is_separate_from_base(
    built_image,
) -> None:
    out, base_sha, base = (
        built_image
    )

    derived = (
        out
        / "rootfs.ext4"
    )

    assert (
        derived.resolve()
        != base.resolve()
    )

    assert not os.path.samefile(
        derived,
        base,
    )

    assert (
        sha256_file(base)
        == base_sha
    )

    manifest = json.loads(
        (
            out
            / "manifest.json"
        ).read_text()
    )

    assert (
        manifest["checks"][
            "base_rootfs_unchanged"
        ]
        is True
    )

    assert (
        manifest["checks"][
            "derived_rootfs_separate"
        ]
        is True
    )


def test_verify_detects_stale_repo_files(
    built_image,
    tmp_path: Path,
) -> None:
    out, base_sha, _ = (
        built_image
    )

    repo_copy = (
        tmp_path
        / "repo"
    )

    for item in GUEST_FILES:
        target = (
            repo_copy
            / item.repo_path
        )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copyfile(
            REPO / item.repo_path,
            target,
        )

    agent = (
        repo_copy
        / GUEST_FILES[1].repo_path
    )

    agent.write_text(
        agent.read_text()
        + "\n# changed\n"
    )

    with pytest.raises(
        PinError,
        match="stale",
    ):
        verify_image(
            out,
            base_sha,
            repo_copy,
        )


def test_verify_detects_tampered_image(
    built_image,
    tmp_path: Path,
) -> None:
    out, base_sha, _ = (
        built_image
    )

    tampered = (
        tmp_path
        / "tampered"
    )

    shutil.copytree(
        out,
        tampered,
    )

    image = (
        tampered
        / "rootfs.ext4"
    )

    os.chmod(
        image,
        0o644,
    )

    subprocess.run(
        [
            "debugfs",
            "-w",
            "-R",
            (
                f'sif "'
                f'{GUEST_FILES[1].guest_path}'
                f'" uid 1000'
            ),
            str(image),
        ],
        capture_output=True,
        check=False,
    )

    inode = stat_inode(
        image,
        GUEST_FILES[1].guest_path,
    )

    assert inode is not None
    assert inode.uid == 1000

    os.chmod(
        image,
        0o444,
    )

    with pytest.raises(
        PinError,
        match="sha256 differs",
    ):
        verify_image(
            tampered,
            base_sha,
            REPO,
        )
