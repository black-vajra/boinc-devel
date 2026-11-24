#!/usr/bin/env python3

"""Sensor-driven supervisor failure-survival fixture.

Synthetic emergency only.
"""

import json
import socket
import sys
import time

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / "scripts"))

from thermal_guardian_supervisor import notify, sample
from thermal_guardian import validate_config
from thermal_guardian_recovery import RecoveryState


def receive(sock):
    raw = sock.recv(4096)

    if not raw:
        raise RuntimeError("Executor disconnected")

    return json.loads(raw)


def main():
    directory = Path(sys.argv[1])

    config = json.loads(
        (
            ROOT / "examples/thermal-guardian-pots.json"
        ).read_text()
    )

    validate_config(config)

    recovery = RecoveryState(
        directory / "operating-state.json"
    )

    if recovery.status() != "CLEAN":
        raise RuntimeError("Recovery authorization required")

    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    ) as sock:

        sock.settimeout(2)

        sock.connect(
            str(directory / "executor.sock")
        )

        if receive(sock)["kind"] != "READY":
            raise RuntimeError("Executor not ready")

        snapshot = sample(config)

        if snapshot["faults"]:
            raise RuntimeError("Required sensor fault")

        if snapshot["level"] != "NORMAL":
            raise RuntimeError("Unsafe initial temperature")

        recovery.arm()

        notify(
            "READY=1\n"
            "STATUS=Survival test supervisor ready"
        )

        print("PASS: Supervisor ready", flush=True)

        while True:
            snapshot = sample(config)

            if snapshot["faults"]:
                raise RuntimeError("Required sensor fault")

            if snapshot["level"] != "NORMAL":
                raise RuntimeError("Unexpected thermal state")

            notify("WATCHDOG=1")

            if (directory / "trigger").exists():

                sock.send(json.dumps({
                    "kind": "THERMAL",
                    "value": "EMERGENCY",
                }).encode())

                event = receive(sock)

                if event["state"] != "COUNTDOWN":
                    raise RuntimeError(
                        "Emergency deadline not established"
                    )

                (directory / "deadline.json").write_text(
                    json.dumps(event)
                )

                print(
                    "PASS: Executor deadline established",
                    flush=True,
                )

                # Keep the connection alive while the test
                # operator deliberately freezes this process.
                while True:
                    notify("WATCHDOG=1")
                    time.sleep(0.25)

            time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
