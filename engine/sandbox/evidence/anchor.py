from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .schema import (
    ANCHOR_SCHEMA,
    EvidenceHead,
    canonical_json,
)


class EvidenceAnchorError(RuntimeError):
    pass


class FileEvidenceAnchor:
    """Durable evidence-chain head checkpoint.

    The anchor is intentionally stored separately from the JSONL ledger.
    Rollback/truncation detection depends on this checkpoint remaining
    newer and independently protected from the ledger being verified.
    """

    def __init__(
        self,
        path: Path,
    ) -> None:
        self.path = Path(path)

    def read(
        self,
    ) -> EvidenceHead | None:
        if not self.path.exists():
            return None

        try:
            raw = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise EvidenceAnchorError(
                "unable to read evidence head anchor"
            ) from exc

        if not isinstance(raw, dict):
            raise EvidenceAnchorError(
                "evidence head anchor is not an object"
            )

        if raw.get("schema") != ANCHOR_SCHEMA:
            raise EvidenceAnchorError(
                "unsupported evidence anchor schema"
            )

        sequence = raw.get("sequence")
        record_hash = raw.get("record_hash")

        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence < 1
        ):
            raise EvidenceAnchorError(
                "invalid evidence anchor sequence"
            )

        if (
            not isinstance(record_hash, str)
            or len(record_hash) != 64
        ):
            raise EvidenceAnchorError(
                "invalid evidence anchor hash"
            )

        return EvidenceHead(
            schema=ANCHOR_SCHEMA,
            sequence=sequence,
            record_hash=record_hash,
        )

    def write(
        self,
        *,
        sequence: int,
        record_hash: str,
    ) -> EvidenceHead:
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence < 1
        ):
            raise EvidenceAnchorError(
                "invalid evidence anchor sequence"
            )

        if (
            not isinstance(record_hash, str)
            or len(record_hash) != 64
        ):
            raise EvidenceAnchorError(
                "invalid evidence anchor hash"
            )

        head = EvidenceHead(
            schema=ANCHOR_SCHEMA,
            sequence=sequence,
            record_hash=record_hash,
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        payload = canonical_json(
            {
                "schema": head.schema,
                "sequence": head.sequence,
                "record_hash": head.record_hash,
            }
        ) + b"\n"

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
        )

        temporary = Path(
            temporary_name
        )

        try:
            os.fchmod(
                fd,
                0o600,
            )

            with os.fdopen(
                fd,
                "wb",
                closefd=True,
            ) as stream:
                stream.write(
                    payload
                )
                stream.flush()
                os.fsync(
                    stream.fileno()
                )

            os.replace(
                temporary,
                self.path,
            )

            directory_fd = os.open(
                self.path.parent,
                os.O_RDONLY
                | getattr(
                    os,
                    "O_DIRECTORY",
                    0,
                ),
            )

            try:
                os.fsync(
                    directory_fd
                )
            finally:
                os.close(
                    directory_fd
                )

        except BaseException:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

            raise

        return head
