#!/usr/bin/env python3

"""Authenticated emergency deadline registration.

Development integration only.
No privileged operations or actual shutdown commands.
"""

import json
import socket
import time

from thermal_guardian_ipc import (
    authorize_peer,
    receive_message,
    ProtocolError,
)


class DeadlineRegistration:

    def __init__(self, sock, expected_uid, expected_pid):
        self.sock = sock

        self.peer = authorize_peer(
            sock, expected_uid, expected_pid
        )

        self.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_PASSCRED,
            1,
        )

        self.sequence = 0

    def __call__(self, decision):
        self.sequence += 1

        payload = {
            "sequence": self.sequence,
            "state": decision.state.value,
            "deadline": decision.deadline,
        }

        message = {
            "kind": "REGISTER",
            "value": json.dumps(
                payload, allow_nan=False
            ),
        }

        # Registration must not indefinitely block
        # the primary emergency executor.
        expires = time.monotonic() + 0.1

        self.sock.settimeout(0.1)

        self.sock.send(
            json.dumps(message).encode()
        )

        remaining = expires - time.monotonic()

        if remaining <= 0:
            raise TimeoutError("Registration timed out")

        self.sock.settimeout(remaining)

        reply = receive_message(
            self.sock,
            "deadline-ack",
            expected_peer=self.peer,
        )

        if reply["value"] != str(self.sequence):
            raise ProtocolError(
                "Registration acknowledgement mismatch"
            )

        return True
