#!/usr/bin/env python3

"""Thermal Guardian sensor-driven supervisor.

Development mode only.
No poweroff authority or hardware modifications.
"""

import argparse
import json
import os
import select
import socket
import time

from pathlib import Path

from thermal_guardian import (
    discover_temperatures,
    discover_gpu,
    evaluate,
    validate_config,
    timestamp,
)

from thermal_guardian_recovery import RecoveryState
from thermal_guardian_latch import EmergencyLatch
from thermal_guardian_ipc import (
    authorize_peer,
    receive_message,
    ProtocolError,
)


def notify(message):
    address = os.environ["NOTIFY_SOCKET"]

    if address.startswith("@"):
        address = "\0" + address[1:]

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_DGRAM,
    ) as sock:

        sock.settimeout(0.5)
        sock.connect(address)
        sock.sendall(message.encode())


def sample(config):
    readings = discover_temperatures()

    level, faults = evaluate(readings, config)

    return {
        "timestamp": timestamp(),
        "level": level,
        "faults": faults,
        "temperatures": readings,
        "gpu": discover_gpu(),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--config", type=Path, required=True
    )

    parser.add_argument(
        "--state-dir", type=Path, required=True
    )

    parser.add_argument("--executor-socket", type=Path)
    parser.add_argument("--executor-pid", type=int)

    args = parser.parse_args()

    if bool(args.executor_socket) != bool(args.executor_pid):
        parser.error("Both executor socket and PID are required")

    # This development supervisor must not run as root.
    if os.geteuid() == 0:
        raise RuntimeError(
            "Development supervisor cannot run as root"
        )

    config = json.loads(args.config.read_text())
    validate_config(config)

    recovery = RecoveryState(
        args.state_dir / "operating-state.json"
    )

    latch = EmergencyLatch(
        args.state_dir / "emergency-latch.json"
    )

    print("=== THERMAL GUARDIAN SUPERVISOR ===", flush=True)
    print("Shutdown authority: DISABLED", flush=True)

    state = recovery.status()

    print(f"Persistent state: {state}", flush=True)

    if state != "CLEAN":
        print("FAIL: Recovery authorization required", flush=True)
        return 2

    if latch.blocks_computation():
        print("FAIL: Emergency latch blocks startup", flush=True)
        return 2

    snapshot = sample(config)

    if snapshot["faults"]:
        print(
            f"FAIL: Required sensor faults: {snapshot['faults']}",
            flush=True,
        )
        return 2

    if snapshot["level"] != "NORMAL":
        print(
            f"FAIL: Unsafe startup state: {snapshot['level']}",
            flush=True,
        )
        return 2

    print("PASS: Required sensors validated", flush=True)

    connection = None
    executor_peer = None

    if args.executor_socket is not None:
        connection = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET,
        )
        connection.settimeout(2)
        connection.connect(str(args.executor_socket))

        executor_peer = authorize_peer(
            connection,
            os.getuid(),
            args.executor_pid,
        )
        connection.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_PASSCRED,
            1,
        )

        ready = json.loads(connection.recv(4096))

        if ready != {"kind": "READY"}:
            raise RuntimeError("Invalid executor readiness")

        connection.settimeout(0.1)

        print("PASS: Authenticated executor connected",
              flush=True)

    recovery.arm()

    print("PASS: Persistent ARMED state established", flush=True)

    notify(
        "READY=1\n"
        "STATUS=Sensor validation complete; guardian armed"
    )

    print("PASS: Guardian READY", flush=True)

    next_status = 0
    emergency_active = False

    def executor_completion():
        """Poll for authenticated completion; None means still running."""
        if connection is None:
            return None

        readable, _, _ = select.select([connection], [], [], 0)
        if not readable:
            return None

        try:
            message = receive_message(
                connection,
                "executor-status",
                expected_peer=executor_peer,
            )
        except EOFError:
            print(
                "FAIL: Executor disconnected without completion acknowledgement",
                flush=True,
            )
            return 7
        except (OSError, ProtocolError, PermissionError) as error:
            print(
                f"FAIL: Invalid executor completion message: {error}",
                flush=True,
            )
            return 9

        if message["kind"] == "ACTION_COMPLETE":
            print(
                "PASS: Authenticated executor action completion",
                flush=True,
            )
            return 0

        print(
            f"FAIL: Executor action failed: {message['value']}",
            flush=True,
        )
        return 9

    while True:
        completed = executor_completion()
        if completed is not None:
            return completed

        started = time.monotonic()

        snapshot = sample(config)

        level = snapshot["level"]
        faults = snapshot["faults"]

        if connection is not None:
            try:
                connection.send(json.dumps({
                    "kind": "THERMAL",
                    "value": (
                        "FAULT"
                        if faults and level not in
                        ("EMERGENCY", "CRITICAL")
                        else level
                    ),
                }).encode())
            except OSError as error:
                # The executor may complete between the pre-send poll and
                # this send. Consume its status packet before classifying EOF.
                completed = executor_completion()
                if completed is not None:
                    return completed

                print(f"FAIL: Executor communication: {error}",
                      flush=True)
                return 7

        if level in ("EMERGENCY", "CRITICAL"):

            if not emergency_active:
                emergency_active = True

                print(
                    f"FAIL: Thermal emergency: {level}",
                    flush=True,
                )

                recovery.emergency(
                    f"Thermal state: {level}"
                )

                reading = next(
                    item for item in snapshot["temperatures"]
                    if item["level"] == level
                )

                policy = next(
                    item for item in config["sensors"]
                    if item["name"] == reading["policy"]
                )

                result = latch.create(
                    sensor=(
                        f"{reading['driver']} "
                        f"{reading['device']} "
                        f"{reading['label']}"
                    ),
                    temperature=reading["temperature"],
                    threshold=policy[level.lower()],
                    level=level,
                    reason="Thermal supervisor emergency",
                )

                if result["state"] != "LATCHED":
                    print("FAIL: Emergency latch persistence",
                          flush=True)
                    return 8

                print("PASS: Persistent emergency recorded",
                      flush=True)

            if connection is None:
                return 3

        if faults:
            print(
                f"FAIL: Required sensor faults: {faults}",
                flush=True,
            )

            # Retain ARMED state to block unattended recovery.
            return 4

        if not emergency_active and latch.blocks_computation():
            print(
                "FAIL: Emergency latch no longer clear",
                flush=True,
            )
            return 5

        expected_state = (
            "EMERGENCY" if emergency_active else "ARMED"
        )

        if recovery.status() != expected_state:
            print(
                "FAIL: Operating state unexpectedly changed",
                flush=True,
            )
            return 6

        # Heartbeat only follows successful sensor sampling
        # and persistent-state verification.
        notify(
            f"WATCHDOG=1\nSTATUS=Thermal state: {level}"
        )

        if started >= next_status:
            print(
                f"{snapshot['timestamp']} | "
                f"State: {level} | "
                f"Sensors: {len(snapshot['temperatures'])} | "
                f"Faults: {len(faults)}",
                flush=True,
            )

            next_status = started + 10

        elapsed = time.monotonic() - started
        delay = max(0, config["poll_interval"] - elapsed)

        if connection is not None:
            readable, _, _ = select.select(
                [connection], [], [], delay
            )
            if readable:
                completed = executor_completion()
                if completed is not None:
                    return completed
        else:
            time.sleep(delay)


if __name__ == "__main__":
    raise SystemExit(main())
