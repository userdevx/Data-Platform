from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping


class TrustStatus(str, Enum):
    TRUSTED = "trusted"
    MISSING = "missing"
    DIGEST_MISMATCH = "digest_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    MODE_MISMATCH = "mode_mismatch"
    OWNER_MISMATCH = "owner_mismatch"
    NOT_REGULAR_FILE = "not_regular_file"
    SYMLINK = "symlink"


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    name: str
    path: Path
    sha256: str
    size_bytes: int | None = None
    owner_uid: int | None = None
    require_read_only: bool = False
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeDescriptor:
    runtime_kind: str
    isolation_class: str
    implemented: bool
    artifacts: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrustReport:
    artifact: str
    status: TrustStatus
    path: Path
    expected_sha256: str
    actual_sha256: str | None = None
    message: str = ""

    @property
    def trusted(self) -> bool:
        return self.status is TrustStatus.TRUSTED
