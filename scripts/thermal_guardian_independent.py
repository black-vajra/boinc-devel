#!/usr/bin/env python3

"""Independent authenticated emergency deadline enforcement."""

import json
import math
import socket
import time

from thermal_guardian_deadline import DeadlineRecord

from thermal_guardian_ipc import (
    authorize_peer,
    receive_message,
    AuthorizationError,
    ProtocolError,
    unique_fields,
)


def run(sock, *, expected_uid, expected_pid,
        state_path, action):

    peer = authorize_peer(
        sock, expected_uid, expected_pid
    )

    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_PASSCRED,
        1,
    )

    store = DeadlineRecord(state_path)

    record = None
    deadline = None
    sequence = 0
    connected = True

    try:
        record = store.load()
        deadline = record["deadline"]

        sequence = (
            2 if record["override_used"] else 1
        )

    except FileNotFoundError:
        pass

    while True:

        now = time.monotonic()

        if deadline is not None and now >= deadline:
            return action(record)

        if not connected:

            if deadline is None:
                return 2

            time.sleep(max(0, deadline - now))
            continue

        timeout = (
            None if deadline is None
            else max(0, deadline - now)
        )

        sock.settimeout(timeout)

        try:
            message = receive_message(
                sock,
                "deadline-registration",
                expected_peer=peer,
            )

        except socket.timeout:
            continue

        except (AuthorizationError, ProtocolError):
            continue

        except (EOFError, OSError):
            connected = False
            continue

        now = time.monotonic()

        if deadline is not None and now >= deadline:
            return action(record)

        try:
            payload = json.loads(
                message["value"],
                object_pairs_hook=unique_fields,
            )

            if not isinstance(payload, dict):
                continue

            if set(payload) != {
                "sequence", "state", "deadline"
            }:
                continue

            number = payload["sequence"]
            proposed = payload["deadline"]
            state = payload["state"]

            if type(number) is not int:
                continue

            if number != sequence + 1:
                continue

            if (
                type(proposed) not in (int, float)
                or not math.isfinite(proposed)
                or proposed <= 0
            ):
                continue

            if record is None:

                if state != "COUNTDOWN":
                    continue

                if proposed > now + 7:
                    continue

                record = store.register(proposed)

            else:

                if state != "OVERRIDE":
                    continue

                record = store.override(
                    record["event_id"],
                    proposed,
                )

            deadline = record["deadline"]
            sequence = number

        except (
            ValueError,
            RuntimeError,
            TypeError,
            OSError,
            OverflowError,
            RecursionError,
        ):
            continue

        # Acknowledge only after successful persistence.
        # Failure to deliver the ACK does not cancel
        # the independent deadline.
        sock.setblocking(False)

        try:
            sock.send(json.dumps({
                "kind": "ACK",
                "value": str(sequence),
            }).encode())

        except OSError:
            pass
