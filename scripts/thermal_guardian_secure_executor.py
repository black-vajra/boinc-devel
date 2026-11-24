#!/usr/bin/env python3

"""Authenticated thermal emergency executor.

Development implementation.
No actual shutdown authority.
"""

import json
import secrets
import selectors
import socket
import time

from thermal_guardian_controller import EmergencyController

from thermal_guardian_ipc import (
    AuthorizationError,
    ProtocolError,
    authorize_peer,
    receive_message,
)


def run(
    thermal_socket,
    operator_socket,
    *,
    thermal_uid,
    operator_uid,
    action,
    countdown=7,
    override=30,
    thermal_pid=None,
    operator_pid=None,
    notify_address=None,
    deadline_registration=None,
):
    if not callable(action):
        raise TypeError("Action must be callable")

    if (deadline_registration is not None
            and not callable(deadline_registration)):
        raise TypeError("Invalid deadline registration callback")

    thermal_peer = authorize_peer(
        thermal_socket,
        thermal_uid,
        thermal_pid,
    )

    operator_peer = authorize_peer(
        operator_socket,
        operator_uid,
        operator_pid,
    )

    controller = EmergencyController(
        countdown=countdown,
        override=override,
    )

    thermal_level = "NORMAL"
    emergency_token = None
    registration_ok = False

    decision = controller.update(
        time.monotonic(),
        thermal_level,
    )

    def execute(decision):
        try:
            result = action(decision)

            if result is not None and not result.accepted:
                return 3

        except Exception:
            return 3

        return 0

    with selectors.DefaultSelector() as selector:

        for sock, channel in (
            (thermal_socket, "thermal"),
            (operator_socket, "operator"),
        ):
            sock.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_PASSCRED,
                1,
            )

            sock.setblocking(False)

            selector.register(
                sock,
                selectors.EVENT_READ,
                channel,
            )

        def systemd_notify(message):
            if notify_address is None:
                return True

            address = notify_address

            if address.startswith("@"):
                address = chr(0) + address[1:]

            try:
                with socket.socket(
                    socket.AF_UNIX,
                    socket.SOCK_DGRAM,
                ) as notifier:

                    notifier.setblocking(False)
                    notifier.sendto(
                        message.encode(),
                        address,
                    )

                return True

            except OSError:
                return False

        if notify_address is not None:
            try:
                thermal_socket.send(json.dumps({
                    "kind": "READY",
                }).encode())

            except OSError:
                return 2

            if not systemd_notify(
                "READY=1" + chr(10) +
                "STATUS=Authenticated executor operational"
            ):
                return 2

        next_heartbeat = time.monotonic()

        def publish_emergency(decision):
            registered = True
            if deadline_registration is not None:
                try:
                    registered = bool(
                        deadline_registration(decision)
                    )
                except Exception:
                    registered = False

            event = {
                "kind": "EMERGENCY_SESSION",
                "token": emergency_token,
                "deadline": decision.deadline,
                "state": decision.state.value,
            }

            try:
                operator_socket.send(
                    json.dumps(event).encode()
                )
            except OSError:
                # Failure to notify the desktop must
                # never delay or cancel the deadline.
                pass

            return registered

        while True:

            # Deadline enforcement must precede polling.
            decision = controller.update(
                time.monotonic(),
                thermal_level,
            )

            if decision.shutdown_requested:
                return execute(decision)

            now = time.monotonic()

            if (
                notify_address is not None
                and now >= next_heartbeat
            ):
                notified = systemd_notify(
                    "WATCHDOG=1" + chr(10) +
                    f"STATUS=Executor {decision.state.value}"
                )

                if (
                    not notified
                    and decision.deadline is None
                ):
                    return 2

                next_heartbeat = now + 1.0

            timeout = None

            if notify_address is not None:
                timeout = max(
                    0,
                    next_heartbeat - time.monotonic(),
                )

            if decision.deadline is not None:
                remaining = max(
                    0,
                    decision.deadline - time.monotonic(),
                )

                timeout = (
                    remaining
                    if timeout is None
                    else min(timeout, remaining)
                )

            events = selector.select(timeout)

            # A continuously readable socket must never
            # postpone an established deadline.
            decision = controller.update(
                time.monotonic(),
                thermal_level,
            )

            if decision.shutdown_requested:
                return execute(decision)

            # Prioritize thermal escalation over operator
            # responses when both channels are readable.
            events.sort(
                key=lambda event: (
                    event[0].data != "thermal"
                )
            )

            for key, _ in events:

                decision = controller.update(
                    time.monotonic(),
                    thermal_level,
                )

                if decision.shutdown_requested:
                    return execute(decision)

                sock = key.fileobj
                channel = key.data

                try:
                    message = receive_message(
                        sock,
                        (
                            "operator-session"
                            if channel == "operator"
                            else channel
                        ),
                        expected_peer=(
                            thermal_peer
                            if channel == "thermal"
                            else operator_peer
                        ),
                    )

                except BlockingIOError:
                    continue

                except (
                    ProtocolError,
                    AuthorizationError,
                ):
                    continue

                except (EOFError, OSError):

                    selector.unregister(sock)

                    if (
                        channel == "thermal"
                        and decision.deadline is None
                    ):
                        return 2

                    # Losing either communication channel
                    # cannot cancel an active emergency.
                    continue

                if channel == "thermal":

                    thermal_level = message["value"]

                    decision = controller.update(
                        time.monotonic(),
                        thermal_level,
                    )

                    if (
                        emergency_token is None
                        and decision.deadline is not None
                        and not decision.shutdown_requested
                    ):
                        emergency_token = secrets.token_hex(32)
                        registration_ok = publish_emergency(decision)

                elif (
                    decision.deadline is not None
                    and emergency_token is not None
                    and secrets.compare_digest(
                        message["token"],
                        emergency_token,
                    )
                ):
                    if (
                        message["value"] == "NO"
                        and deadline_registration is not None
                        and not registration_ok
                    ):
                        continue

                    previous_deadline = decision.deadline

                    decision = controller.update(
                        time.monotonic(),
                        thermal_level,
                        operator=message["value"],
                    )

                    if (
                        not decision.shutdown_requested
                        and decision.deadline != previous_deadline
                    ):
                        registration_ok = publish_emergency(decision)
                        if not registration_ok:
                            decision = controller.request_shutdown(
                                "Independent override registration failed"
                            )

                if decision.shutdown_requested:
                    return execute(decision)
