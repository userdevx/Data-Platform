from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import ArtifactDescriptor, RuntimeDescriptor, TrustReport
from .trust import ArtifactTrustError, verify_artifact


class RegistryError(RuntimeError):
    pass


class RuntimeImageRegistry:
    """Registry of runtime descriptors and externally stored artifacts.

    Registration does not itself establish trust. Trust is established only
    by verification of each registered artifact against its descriptor.
    """

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        self._runtimes: dict[str, RuntimeDescriptor] = {}
        self._artifacts: dict[str, ArtifactDescriptor] = {}

    @property
    def runtimes(self) -> tuple[RuntimeDescriptor, ...]:
        return tuple(
            self._runtimes[key]
            for key in sorted(self._runtimes)
        )

    @property
    def artifacts(self) -> tuple[ArtifactDescriptor, ...]:
        return tuple(
            self._artifacts[key]
            for key in sorted(self._artifacts)
        )

    def register_runtime(
        self,
        descriptor: RuntimeDescriptor,
    ) -> None:
        if descriptor.runtime_kind in self._runtimes:
            raise RegistryError(
                f"runtime already registered: "
                f"{descriptor.runtime_kind}"
            )

        missing = [
            name
            for name in descriptor.artifacts
            if name not in self._artifacts
        ]

        if missing:
            raise RegistryError(
                "runtime references unregistered artifacts: "
                + ", ".join(sorted(missing))
            )

        self._runtimes[descriptor.runtime_kind] = descriptor

    def register_artifact(
        self,
        descriptor: ArtifactDescriptor,
    ) -> None:
        if descriptor.name in self._artifacts:
            raise RegistryError(
                f"artifact already registered: {descriptor.name}"
            )

        if (
            len(descriptor.sha256) != 64
            or any(
                char not in "0123456789abcdef"
                for char in descriptor.sha256
            )
        ):
            raise RegistryError(
                f"artifact has invalid sha256: {descriptor.name}"
            )

        self._artifacts[descriptor.name] = descriptor

    def runtime(
        self,
        runtime_kind: str,
    ) -> RuntimeDescriptor:
        try:
            return self._runtimes[runtime_kind]
        except KeyError as exc:
            raise RegistryError(
                f"unknown runtime: {runtime_kind}"
            ) from exc

    def artifact(
        self,
        name: str,
    ) -> ArtifactDescriptor:
        try:
            return self._artifacts[name]
        except KeyError as exc:
            raise RegistryError(
                f"unknown artifact: {name}"
            ) from exc

    def verify_artifact(
        self,
        name: str,
        *,
        raise_on_failure: bool = True,
    ) -> TrustReport:
        return verify_artifact(
            self.artifact(name),
            raise_on_failure=raise_on_failure,
        )

    def verify_runtime(
        self,
        runtime_kind: str,
    ) -> tuple[TrustReport, ...]:
        runtime = self.runtime(runtime_kind)

        if not runtime.implemented:
            raise RegistryError(
                "runtime is reserved but not implemented: "
                f"{runtime_kind}"
            )

        return tuple(
            self.verify_artifact(
                name,
                raise_on_failure=False,
            )
            for name in runtime.artifacts
        )

    def assert_trusted(
        self,
        runtime_kind: str,
    ) -> None:
        reports = self.verify_runtime(runtime_kind)

        failures = [
            report
            for report in reports
            if not report.trusted
        ]

        if failures:
            raise ArtifactTrustError(
                "; ".join(
                    report.message
                    for report in failures
                )
            )

    def write_manifest(
        self,
        path: Path,
    ) -> None:
        """Write an atomic registry snapshot.

        This snapshot describes current registry state. It is not itself a
        trust root; runtime-specific tracked manifests remain authoritative.
        """

        data = {
            "schema_version": self.SCHEMA_VERSION,
            "runtimes": [
                {
                    "runtime_kind": item.runtime_kind,
                    "isolation_class": item.isolation_class,
                    "implemented": item.implemented,
                    "artifacts": list(item.artifacts),
                    "metadata": dict(item.metadata),
                }
                for item in self.runtimes
            ],
            "artifacts": [
                {
                    "name": item.name,
                    "path": str(item.path),
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                    "owner_uid": item.owner_uid,
                    "require_read_only": item.require_read_only,
                    "metadata": dict(item.metadata),
                }
                for item in self.artifacts
            ],
        }

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        fd, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
            text=True,
        )

        temporary_path = Path(temporary)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(
                    data,
                    stream,
                    indent=2,
                    sort_keys=True,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
