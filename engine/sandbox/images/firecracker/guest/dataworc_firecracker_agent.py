#!/usr/bin/python3
"""DataWorc Firecracker guest agent.

Serves the shared guest execution protocol over AF_VSOCK.
"""

from __future__ import annotations

import socket
import sys
import time


sys.path.insert(
    0,
    "/usr/local/lib/dataworc",
)

from dataworc_guest_exec import serve_connection  # noqa: E402


VSOCK_PORT = 5000


def main() -> None:
    listener: socket.socket | None = None

    while listener is None:
        candidate: socket.socket | None = None

        try:
            candidate = socket.socket(
                socket.AF_VSOCK,
                socket.SOCK_STREAM,
            )

            candidate.bind(
                (
                    socket.VMADDR_CID_ANY,
                    VSOCK_PORT,
                )
            )

            candidate.listen(1)
            listener = candidate

        except OSError:
            if candidate is not None:
                candidate.close()

            time.sleep(0.25)

    while True:
        connection, _ = listener.accept()

        with connection:
            with connection.makefile(
                "rwb",
                buffering=0,
            ) as stream:
                try:
                    serve_connection(stream)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
