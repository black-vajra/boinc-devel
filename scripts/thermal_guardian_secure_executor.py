#!/usr/bin/env python3

"""Authenticated thermal emergency executor.

Development implementation.
No actual shutdown authority.
"""

import selectors
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
):
    if not callable(action):
        raise TypeError("Action must be callable")

    authorize_peer(
        thermal_socket,
        thermal_uid,
        thermal_pid,
    )

    authorize_peer(
        operator_socket,
        operator_uid,
        operator_pid,
    )

    controller = EmergencyController(
        countdown=countdown,
        override=override,
    )

    thermal_level = "NORMAL"

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
            sock.setblocking(False)

            selector.register(
                sock,
                selectors.EVENT_READ,
                channel,
            )

        while True:

            # Deadline enforcement must precede polling.
            decision = controller.update(
                time.monotonic(),
                thermal_level,
            )

            if decision.shutdown_requested:
                return execute(decision)

            timeout = None

            if decision.deadline is not None:
                timeout = max(
                    0,
                    decision.deadline - time.monotonic(),
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
                        channel,
                    )

                except BlockingIOError:
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

                except (
                    ProtocolError,
                    AuthorizationError,
                ):
                    continue

                if channel == "thermal":

                    thermal_level = message["value"]

                    decision = controller.update(
                        time.monotonic(),
                        thermal_level,
                    )

                elif decision.deadline is not None:

                    decision = controller.update(
                        time.monotonic(),
                        thermal_level,
                        operator=message["value"],
                    )

                if decision.shutdown_requested:
                    return execute(decision)
