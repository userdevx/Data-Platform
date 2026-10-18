from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from .models import ArtifactDescriptor, TrustReport, TrustStatus


class ArtifactTrustError(RuntimeError):
    pass


def sha256_file(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _report(
    descriptor: ArtifactDescriptor,
    status: TrustStatus,
    *,
    actual_sha256: str | None = None,
    message: str = "",
) -> TrustReport:
    return TrustReport(
        artifact=descriptor.name,
        status=status,
        path=descriptor.path,
        expected_sha256=descriptor.sha256,
        actual_sha256=actual_sha256,
        message=message,
    )


def _finish(
    report: TrustReport,
    raise_on_failure: bool,
) -> TrustReport:
    if raise_on_failure and not report.trusted:
        raise ArtifactTrustError(report.message)

    return report


def verify_artifact(
    descriptor: ArtifactDescriptor,
    *,
    raise_on_failure: bool = True,
) -> TrustReport:
    path = descriptor.path.expanduser()

    if path.is_symlink():
        return _finish(
            _report(
                descriptor,
                TrustStatus.SYMLINK,
                message=f"trusted artifact must not be a symlink: {path}",
            ),
            raise_on_failure,
        )

    try:
        info = path.stat()
    except FileNotFoundError:
        return _finish(
            _report(
                descriptor,
                TrustStatus.MISSING,
                message=f"artifact does not exist: {path}",
            ),
            raise_on_failure,
        )

    if not stat.S_ISREG(info.st_mode):
        return _finish(
            _report(
                descriptor,
                TrustStatus.NOT_REGULAR_FILE,
                message=f"artifact is not a regular file: {path}",
            ),
            raise_on_failure,
        )

    if (
        descriptor.owner_uid is not None
        and info.st_uid != descriptor.owner_uid
    ):
        return _finish(
            _report(
                descriptor,
                TrustStatus.OWNER_MISMATCH,
                message=(
                    f"uid mismatch: expected {descriptor.owner_uid}, "
                    f"got {info.st_uid}"
                ),
            ),
            raise_on_failure,
        )

    if descriptor.require_read_only and info.st_mode & (
        stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    ):
        return _finish(
            _report(
                descriptor,
                TrustStatus.MODE_MISMATCH,
                message=f"trusted artifact is writable: {path}",
            ),
            raise_on_failure,
        )

    if (
        descriptor.size_bytes is not None
        and info.st_size != descriptor.size_bytes
    ):
        return _finish(
            _report(
                descriptor,
                TrustStatus.SIZE_MISMATCH,
                message=(
                    f"size mismatch: expected {descriptor.size_bytes}, "
                    f"got {info.st_size}"
                ),
            ),
            raise_on_failure,
        )

    actual = sha256_file(path)

    if actual != descriptor.sha256:
        return _finish(
            _report(
                descriptor,
                TrustStatus.DIGEST_MISMATCH,
                actual_sha256=actual,
                message=(
                    f"sha256 mismatch for {path}: "
                    f"expected {descriptor.sha256}, got {actual}"
                ),
            ),
            raise_on_failure,
        )

    return _report(
        descriptor,
        TrustStatus.TRUSTED,
        actual_sha256=actual,
        message="artifact verified",
    )
