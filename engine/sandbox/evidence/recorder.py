from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from .anchor import (
    EvidenceAnchorError,
    FileEvidenceAnchor,
)
from .schema import (
    EVIDENCE_SCHEMA,
    GENESIS_HASH,
    EvidenceSchemaError,
    canonical_json,
    validate_json_value,
)


class EvidenceIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    schema: str
    sequence: int
    timestamp: str
    event_type: str
    execution_id: str
    data: dict[str, Any]
    previous_hash: str
    record_hash: str


class EvidenceRecorder:
    """Append-only, hash-chained sandbox evidence ledger."""

    GENESIS = GENESIS_HASH

    def __init__(
        self,
        path: Path,
        *,
        anchor_path: Path | None = None,
    ) -> None:
        self.path = Path(
            path
        )

        self.anchor = FileEvidenceAnchor(
            anchor_path
            if anchor_path is not None
            else self.path.with_suffix(
                self.path.suffix + ".head"
            )
        )

        self.lock_path = (
            self.path.with_suffix(
                self.path.suffix + ".lock"
            )
        )

    def _records(
        self,
    ) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        records: list[
            dict[str, Any]
        ] = []

        try:
            with self.path.open(
                "r",
                encoding="utf-8",
            ) as stream:
                for line_number, line in enumerate(
                    stream,
                    start=1,
                ):
                    if not line.strip():
                        continue

                    try:
                        record = json.loads(
                            line
                        )
                    except json.JSONDecodeError as exc:
                        raise EvidenceIntegrityError(
                            "invalid JSON in evidence ledger "
                            f"at line {line_number}"
                        ) from exc

                    if not isinstance(
                        record,
                        dict,
                    ):
                        raise EvidenceIntegrityError(
                            "evidence record is not an object "
                            f"at line {line_number}"
                        )

                    records.append(
                        record
                    )

        except OSError as exc:
            raise EvidenceIntegrityError(
                "unable to read evidence ledger"
            ) from exc

        return records

    @staticmethod
    def _validate_record_shape(
        record: dict[str, Any],
        *,
        sequence: int,
    ) -> None:
        required = {
            "schema",
            "sequence",
            "timestamp",
            "event_type",
            "execution_id",
            "data",
            "previous_hash",
            "record_hash",
        }

        if set(record) != required:
            raise EvidenceIntegrityError(
                "unexpected evidence record fields "
                f"at sequence {sequence}"
            )

        if (
            record["schema"]
            != EVIDENCE_SCHEMA
        ):
            raise EvidenceIntegrityError(
                "unsupported evidence schema "
                f"at sequence {sequence}"
            )

        if (
            not isinstance(
                record["sequence"],
                int,
            )
            or isinstance(
                record["sequence"],
                bool,
            )
        ):
            raise EvidenceIntegrityError(
                "invalid evidence sequence type"
            )

        for field in (
            "timestamp",
            "event_type",
            "execution_id",
            "previous_hash",
            "record_hash",
        ):
            if not isinstance(
                record[field],
                str,
            ):
                raise EvidenceIntegrityError(
                    f"invalid evidence field {field}"
                )

        if not isinstance(
            record["data"],
            dict,
        ):
            raise EvidenceIntegrityError(
                "evidence data must be an object"
            )

        try:
            validate_json_value(
                record["data"]
            )
        except EvidenceSchemaError as exc:
            raise EvidenceIntegrityError(
                "invalid evidence data"
            ) from exc

    def _verify_unlocked(
        self,
    ) -> tuple[
        int,
        str,
    ]:
        records = self._records()

        previous_hash = (
            self.GENESIS
        )

        for expected_sequence, record in enumerate(
            records,
            start=1,
        ):
            self._validate_record_shape(
                record,
                sequence=expected_sequence,
            )

            if (
                record["sequence"]
                != expected_sequence
            ):
                raise EvidenceIntegrityError(
                    "evidence sequence is not contiguous"
                )

            if (
                record["previous_hash"]
                != previous_hash
            ):
                raise EvidenceIntegrityError(
                    "evidence previous_hash mismatch"
                )

            stored_hash = (
                record["record_hash"]
            )

            if len(
                stored_hash
            ) != 64:
                raise EvidenceIntegrityError(
                    "invalid evidence record hash"
                )

            body = dict(
                record
            )

            body.pop(
                "record_hash"
            )

            actual_hash = hashlib.sha256(
                canonical_json(
                    body
                )
            ).hexdigest()

            if (
                actual_hash
                != stored_hash
            ):
                raise EvidenceIntegrityError(
                    "evidence hash mismatch at sequence "
                    f"{expected_sequence}"
                )

            previous_hash = (
                stored_hash
            )

        try:
            anchor = self.anchor.read()
        except EvidenceAnchorError as exc:
            raise EvidenceIntegrityError(
                "evidence anchor is invalid"
            ) from exc

        if not records:
            if anchor is not None:
                raise EvidenceIntegrityError(
                    "evidence ledger missing but anchor exists"
                )

            return (
                0,
                self.GENESIS,
            )

        if anchor is None:
            raise EvidenceIntegrityError(
                "evidence ledger exists without durable head anchor"
            )

        if (
            anchor.sequence
            != len(records)
        ):
            raise EvidenceIntegrityError(
                "evidence ledger length does not match head anchor"
            )

        if (
            anchor.record_hash
            != previous_hash
        ):
            raise EvidenceIntegrityError(
                "evidence ledger head does not match anchor"
            )

        return (
            len(records),
            previous_hash,
        )

    def verify(
        self,
    ) -> int:
        self.lock_path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        with self.lock_path.open(
            "a+",
            encoding="utf-8",
        ) as lock:
            os.chmod(
                self.lock_path,
                0o600,
            )

            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_SH,
            )

            try:
                count, _ = (
                    self._verify_unlocked()
                )

                return count
            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )

    def append(
        self,
        *,
        event_type: str,
        execution_id: str,
        data: dict[str, Any],
    ) -> EvidenceRecord:
        if (
            not isinstance(
                event_type,
                str,
            )
            or not event_type.strip()
        ):
            raise ValueError(
                "event_type must be a non-empty string"
            )

        if (
            not isinstance(
                execution_id,
                str,
            )
            or not execution_id.strip()
        ):
            raise ValueError(
                "execution_id must be a non-empty string"
            )

        if not isinstance(
            data,
            dict,
        ):
            raise ValueError(
                "data must be a dictionary"
            )

        validate_json_value(
            data
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        self.lock_path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        with self.lock_path.open(
            "a+",
            encoding="utf-8",
        ) as lock:
            os.chmod(
                self.lock_path,
                0o600,
            )

            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                sequence, previous_hash = (
                    self._verify_unlocked()
                )

                sequence += 1

                body = {
                    "schema": EVIDENCE_SCHEMA,
                    "sequence": sequence,
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "event_type": (
                        event_type.strip()
                    ),
                    "execution_id": (
                        execution_id.strip()
                    ),
                    "data": data,
                    "previous_hash": (
                        previous_hash
                    ),
                }

                record_hash = hashlib.sha256(
                    canonical_json(
                        body
                    )
                ).hexdigest()

                record = EvidenceRecord(
                    **body,
                    record_hash=record_hash,
                )

                with self.path.open(
                    "a",
                    encoding="utf-8",
                ) as stream:
                    os.chmod(
                        self.path,
                        0o600,
                    )

                    stream.write(
                        canonical_json(
                            asdict(
                                record
                            )
                        ).decode(
                            "utf-8"
                        )
                        + "\n"
                    )

                    stream.flush()
                    os.fsync(
                        stream.fileno()
                    )

                # Update the durable checkpoint only after
                # the ledger record itself is durable.
                self.anchor.write(
                    sequence=sequence,
                    record_hash=record_hash,
                )

                return record

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )
